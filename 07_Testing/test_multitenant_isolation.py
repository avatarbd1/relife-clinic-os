import asyncio
import os
import sys
import unittest
from pathlib import Path


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


if __name__ == "__main__":
    unittest.main()

