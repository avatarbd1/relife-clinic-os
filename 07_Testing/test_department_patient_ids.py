import os, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("GOOGLE_SHEET_ID", "physio")
os.environ.setdefault("DENTAL_GOOGLE_SHEET_ID", "dental")
cred = ROOT / "credentials.json"
made = not cred.exists()
if made:
    cred.write_text("{}")

import sheet_scope, sheets


def tearDownModule():
    if made:
        cred.unlink(missing_ok=True)


class FakeWorksheet:
    def __init__(self, ids):
        self.ids = ids

    def col_values(self, _column):
        return ["Patient_ID", *self.ids]


class DepartmentPatientIdTests(unittest.TestCase):
    def tearDown(self):
        sheet_scope._sheet_override.set(None)

    def test_physio_keeps_existing_pt_namespace(self):
        with sheet_scope.use_sheet("physio"):
            value = sheets._next_patient_id(
                FakeWorksheet(["PT0001", "PT0101", "DT9999"])
            )
        self.assertEqual(value, "PT0102")

    def test_dental_uses_dt_namespace(self):
        with sheet_scope.use_sheet("dental"):
            value = sheets._next_patient_id(
                FakeWorksheet(["DT0001", "PT9999"])
            )
        self.assertEqual(value, "DT0002")

    def test_dental_starts_at_dt0001_when_empty(self):
        with sheet_scope.use_sheet("dental"):
            value = sheets._next_patient_id(FakeWorksheet([]))
        self.assertEqual(value, "DT0001")

    def test_malformed_ids_are_ignored(self):
        with sheet_scope.use_sheet("dental"):
            value = sheets._next_patient_id(
                FakeWorksheet(["DTX", "DT0007", "", "PT0008"])
            )
        self.assertEqual(value, "DT0008")


if __name__ == "__main__":
    unittest.main()
