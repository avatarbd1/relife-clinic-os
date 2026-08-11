import asyncio
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch


BOT_DIR = Path(__file__).resolve().parents[1] / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("GOOGLE_SHEET_ID", "LEGACY_TEST_SHEET")
os.environ.setdefault("GOOGLE_CREDENTIALS_PATH", __file__)

from tenant_runtime import (  # noqa: E402
    MasterTenantResolver,
    TenantAccessError,
    TenantIdentity,
    bind_tenant,
    current_tenant,
    reset_tenant,
)
import config  # noqa: E402
import sheets  # noqa: E402


class FakeWorksheet:
    def __init__(self, records):
        self.records = records

    def get_all_records(self):
        return [dict(row) for row in self.records]

    def row_values(self, _row):
        return list(self.records[0]) if self.records else []


class FakeSpreadsheet:
    def __init__(self, tabs):
        self.tabs = tabs

    def worksheet(self, name):
        return FakeWorksheet(self.tabs[name])


class FakeClient:
    def __init__(self, tabs):
        self.sheet = FakeSpreadsheet(tabs)

    def open_by_key(self, _sheet_id):
        return self.sheet


def master_tabs():
    return {
        "Clinics": [
            {"Clinic_ID": "C01", "Clinic_Name": "One", "Sheet_ID": "S01", "Status": "Active"},
            {"Clinic_ID": "C02", "Clinic_Name": "Two", "Sheet_ID": "S02", "Status": "Active"},
        ],
        "Staff_Directory": [
            {"Telegram_ID": "101", "Clinic_ID": "C01", "Status": "Active"},
            {"Telegram_ID": "202", "Clinic_ID": "C02", "Status": "Active"},
        ],
    }


class TenantResolverTests(unittest.TestCase):
    def test_resolves_two_staff_to_different_immutable_tenants(self):
        resolver = MasterTenantResolver(FakeClient(master_tabs()), "MASTER", cache_ttl=60)
        one = resolver.resolve(101)
        two = resolver.resolve(202)
        self.assertEqual((one.clinic_id, one.sheet_id), ("C01", "S01"))
        self.assertEqual((two.clinic_id, two.sheet_id), ("C02", "S02"))
        self.assertNotEqual(one.sheet_id, two.sheet_id)

    def test_duplicate_active_telegram_mapping_fails_closed(self):
        tabs = master_tabs()
        tabs["Staff_Directory"].append(
            {"Telegram_ID": "101", "Clinic_ID": "C02", "Status": "Active"}
        )
        resolver = MasterTenantResolver(FakeClient(tabs), "MASTER", cache_ttl=60)
        with self.assertRaises(TenantAccessError):
            resolver.resolve(101)

    def test_context_binding_propagates_to_worker_thread_and_resets(self):
        tenant = TenantIdentity("C01", "One", "S01")

        async def scenario():
            token = bind_tenant(tenant)
            try:
                return await asyncio.to_thread(current_tenant)
            finally:
                reset_tenant(token)

        result = asyncio.run(scenario())
        self.assertEqual(result, tenant)
        with self.assertRaises(TenantAccessError):
            current_tenant()

    def test_cache_key_contains_sheet_identity_and_rejects_other_tenant(self):
        class FakeClinicWorksheet:
            title = "02_Patients"
            id = 77

            def __init__(self, spreadsheet_id):
                self.spreadsheet_id = spreadsheet_id

        previous = config.MULTITENANT_ENABLED
        config.MULTITENANT_ENABLED = True
        token = bind_tenant(TenantIdentity("C01", "One", "S01"))
        try:
            self.assertEqual(
                sheets._records_cache_key(FakeClinicWorksheet("S01")),
                ("S01", 77),
            )
            with self.assertRaises(RuntimeError):
                sheets._records_cache_key(FakeClinicWorksheet("S02"))
        finally:
            reset_tenant(token)
            config.MULTITENANT_ENABLED = previous

    def test_write_invalidation_forces_fresh_read_without_touching_other_clinic(self):
        class CacheWorksheet:
            title = "02_Patients"
            id = 77
            row_count = 2

            def __init__(self, spreadsheet_id, records):
                self.spreadsheet_id = spreadsheet_id
                self.records = records
                self.read_count = 0

            def get_all_records(self):
                self.read_count += 1
                return [dict(row) for row in self.records]

        previous = config.MULTITENANT_ENABLED
        config.MULTITENANT_ENABLED = True
        clinic_one = CacheWorksheet("S01", [{"Patient_ID": "P1", "Due": 100}])
        other_key = ("S02", 77)
        token = bind_tenant(TenantIdentity("C01", "One", "S01"))
        try:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            sheets._records_cache[other_key] = (
                time.monotonic(),
                [{"Patient_ID": "P2", "Due": 500}],
            )

            first = sheets.safe_get_all_records(clinic_one)
            clinic_one.records = [{"Patient_ID": "P1", "Due": 40}]
            cached = sheets.safe_get_all_records(clinic_one)
            self.assertEqual(first[0]["Due"], 100)
            self.assertEqual(cached[0]["Due"], 100)
            self.assertEqual(clinic_one.read_count, 1)

            sheets._invalidate_cache(clinic_one)
            fresh = sheets.safe_get_all_records(clinic_one)
            self.assertEqual(fresh[0]["Due"], 40)
            self.assertEqual(clinic_one.read_count, 2)
            self.assertIn(other_key, sheets._records_cache)
        finally:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            reset_tenant(token)
            config.MULTITENANT_ENABLED = previous

    def test_write_during_inflight_read_discards_stale_result(self):
        class RacingWorksheet:
            title = "02_Patients"
            id = 77
            row_count = 2
            spreadsheet_id = "S01"

            def __init__(self):
                self.records = [{"Patient_ID": "P1", "Due": 100}]
                self.read_count = 0

            def get_all_records(self):
                self.read_count += 1
                snapshot = [dict(row) for row in self.records]
                if self.read_count == 1:
                    self.records = [{"Patient_ID": "P1", "Due": 40}]
                    sheets._invalidate_cache(self)
                return snapshot

        previous = config.MULTITENANT_ENABLED
        config.MULTITENANT_ENABLED = True
        token = bind_tenant(TenantIdentity("C01", "One", "S01"))
        worksheet = RacingWorksheet()
        try:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            result = sheets.safe_get_all_records(worksheet)
            self.assertEqual(result[0]["Due"], 40)
            self.assertEqual(worksheet.read_count, 2)
        finally:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            reset_tenant(token)
            config.MULTITENANT_ENABLED = previous

    def test_batch_read_uses_one_request_and_populates_tenant_cache(self):
        class BatchWorksheet:
            def __init__(self, title, worksheet_id):
                self.title = title
                self.id = worksheet_id
                self.spreadsheet_id = "S01"

        class BatchSpreadsheet:
            def __init__(self):
                self.calls = []

            def values_batch_get(self, ranges, params=None):
                self.calls.append((list(ranges), params))
                datasets = {
                    "'02_Patients'": [["Patient_ID", "Due"], ["P1", "100"]],
                    "'06_Payments'": [["Receipt_No", "Amount"], ["R1", "60"]],
                }
                return {
                    "valueRanges": [{"values": datasets[item]} for item in ranges]
                }

        previous = config.MULTITENANT_ENABLED
        config.MULTITENANT_ENABLED = True
        token = bind_tenant(TenantIdentity("C01", "One", "S01"))
        fake_sheet = BatchSpreadsheet()
        worksheets = {
            "02_Patients": BatchWorksheet("02_Patients", 2),
            "06_Payments": BatchWorksheet("06_Payments", 6),
        }
        try:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            with patch.object(sheets, "_worksheet", side_effect=worksheets.get), patch.object(
                sheets, "_get_spreadsheet", return_value=fake_sheet
            ):
                first = sheets.batch_get_records(["02_Patients", "06_Payments"])
                second = sheets.batch_get_records(["02_Patients", "06_Payments"])

            self.assertEqual(len(fake_sheet.calls), 1)
            self.assertEqual(first, second)
            self.assertEqual(first["02_Patients"][0]["Due"], 100)
            self.assertEqual(first["06_Payments"][0]["Amount"], 60)
        finally:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            reset_tenant(token)
            config.MULTITENANT_ENABLED = previous

    def test_multi_cell_financial_update_uses_one_batch_and_invalidates_cache(self):
        class WriteWorksheet:
            title = "02_Patients"
            id = 2
            spreadsheet_id = "S01"

            def __init__(self):
                self.calls = []

            def batch_update(self, data, value_input_option=None):
                self.calls.append((data, value_input_option))

        previous = config.MULTITENANT_ENABLED
        config.MULTITENANT_ENABLED = True
        token = bind_tenant(TenantIdentity("C01", "One", "S01"))
        worksheet = WriteWorksheet()
        key = ("S01", 2)
        try:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            sheets._records_cache[key] = (time.monotonic(), [{"Due": 100}])

            sheets._batch_update_cells(
                worksheet,
                4,
                {20: "Paid", 22: 100, 23: 0, 29: "2026-08-11 10:00 AM"},
            )

            self.assertEqual(len(worksheet.calls), 1)
            data, value_input_option = worksheet.calls[0]
            self.assertEqual(value_input_option, "USER_ENTERED")
            self.assertEqual(
                [item["range"] for item in data],
                ["T4", "V4", "W4", "AC4"],
            )
            self.assertNotIn(key, sheets._records_cache)
            self.assertEqual(sheets._records_cache_generation[key], 1)
        finally:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            reset_tenant(token)
            config.MULTITENANT_ENABLED = previous

    def test_multiple_sessions_update_package_in_one_request(self):
        class PackageWorksheet:
            title = "11_Packages"
            id = 11
            spreadsheet_id = "S01"

            def __init__(self):
                self.calls = []

            def batch_update(self, data, value_input_option=None):
                self.calls.append((data, value_input_option))

        previous = config.MULTITENANT_ENABLED
        config.MULTITENANT_ENABLED = True
        token = bind_tenant(TenantIdentity("C01", "One", "S01"))
        worksheet = PackageWorksheet()
        package = {
            "Sessions_Used": 2,
            "Total_Sessions": 10,
            "_row_number": 4,
        }
        try:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            with patch.object(
                sheets, "get_active_package_for_patient", return_value=package
            ), patch.object(sheets, "_worksheet", return_value=worksheet):
                self.assertTrue(sheets.increment_package_session("P1", count=3))

            self.assertEqual(len(worksheet.calls), 1)
            data, _ = worksheet.calls[0]
            self.assertEqual([item["range"] for item in data], ["E4", "F4"])
            self.assertEqual([item["values"][0][0] for item in data], [5, 5])
        finally:
            sheets._records_cache.clear()
            sheets._records_cache_generation.clear()
            reset_tenant(token)
            config.MULTITENANT_ENABLED = previous


if __name__ == "__main__":
    unittest.main()
