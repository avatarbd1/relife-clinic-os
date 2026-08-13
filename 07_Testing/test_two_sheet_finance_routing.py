import os, sys, unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("GOOGLE_SHEET_ID", "physio")
os.environ.setdefault("DENTAL_GOOGLE_SHEET_ID", "dental")
cred = ROOT / "credentials.json"
made = not cred.exists()
if made:
    cred.write_text("{}")

import config, data_contract, sheet_scope, sheets


def tearDownModule():
    if made:
        cred.unlink(missing_ok=True)


class TwoSheetFinanceRoutingTests(unittest.TestCase):
    def tearDown(self):
        sheet_scope._sheet_override.set(None)

    def test_department_sheet_mapping(self):
        self.assertEqual(config.sheet_id_for_department("Physio"), "physio")
        self.assertEqual(config.sheet_id_for_department("Dental"), "dental")

    def test_dental_metadata_uses_dental_clinic_id(self):
        with sheet_scope.use_sheet("dental"):
            active = "RELIFE-DENTAL" if sheets._active_sheet_id() == config.DENTAL_GOOGLE_SHEET_ID else "RELIFE-PHYSIO"
            value = data_contract.metadata("expense", legacy_record_id="EX0001", clinic_id=active)
        self.assertEqual(value["Clinic_ID"], "RELIFE-DENTAL")
        self.assertEqual(value["Record_ID"], "RELIFE-DENTAL:EX0001")

    def test_explicit_dental_approval_binds_dental_sheet(self):
        seen = []
        def fake(*args, **kwargs):
            seen.append(sheets._active_sheet_id())
            return {"ok": True}
        with patch.object(sheets, "finalize_expense_request", side_effect=fake):
            result = sheets.finalize_expense_request_for_department(
                "Dental", "EX0001", "Owner", "Approved", {"Dental"}
            )
        self.assertTrue(result["ok"])
        self.assertEqual(seen, ["dental"])

    def test_legacy_duplicate_fails_closed(self):
        class WS:
            def __init__(self, sid): self.sid = sid
        def fake_ws(_): return WS(sheets._active_sheet_id())
        def fake_records(ws):
            return [{"Expense_ID": "EX0001", "Department": "Dental"}]
        with patch.object(sheets, "_worksheet", side_effect=fake_ws), patch.object(
            sheets, "safe_get_all_records", side_effect=fake_records
        ):
            result = sheets.finalize_expense_request_legacy(
                "EX0001", "Owner", "Approved", {"Physio", "Dental"}
            )
        self.assertEqual(result["reason"], "ambiguous_department")


if __name__ == "__main__":
    unittest.main()
