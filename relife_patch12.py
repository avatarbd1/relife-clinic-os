#!/usr/bin/env python3
"""Use PT IDs for Physio patients and DT IDs for Dental patients."""
from pathlib import Path

ROOT = Path.home() / "relife-clinic-os"
SHEETS = ROOT / "03_Bot" / "sheets.py"
BOT = ROOT / "03_Bot" / "bot.py"
TEST = ROOT / "07_Testing" / "test_department_patient_ids.py"


def edit(path, old, new, label):
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: ✅ already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"❌ {label}: anchor count {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: ✅ applied")


edit(SHEETS, '''def _next_patient_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("PT"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"PT{next_num:04d}"
''', '''def _patient_id_prefix() -> str:
    """Patient namespace follows the active department workbook."""
    if (
        config.DENTAL_GOOGLE_SHEET_ID
        and str(_active_sheet_id()) == str(config.DENTAL_GOOGLE_SHEET_ID)
    ):
        return "DT"
    return "PT"


def _next_patient_id(ws) -> str:
    prefix = _patient_id_prefix()
    ids = ws.col_values(1)[1:]
    numbers = []
    for value in ids:
        value = str(value or "").strip().upper()
        if value.startswith(prefix):
            try:
                numbers.append(int(value[len(prefix):]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"{prefix}{next_num:04d}"
''', "department patient ID generator")

edit(BOT, '''            "❌ তালিকা থেকে সঠিক Patient ID লেখো (উদাহরণ: PT0001), অথবা /cancel দাও।"
''', '''            "❌ তালিকা থেকে সঠিক Patient ID লেখো (যেমন: PT0001 অথবা DT0001), অথবা /cancel দাও।"
''', "patient ID help supports Dental")

TEST.write_text('''import os, sys, unittest
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
''', encoding="utf-8")
print("test_department_patient_ids.py: ✅ created")
print("\nRun:")
print("python3 -m py_compile 03_Bot/sheets.py 03_Bot/bot.py")
print("python3 -m unittest 07_Testing/test_department_patient_ids.py 07_Testing/test_two_sheet_router.py 07_Testing/test_department_access.py -v")
print("git add 03_Bot/sheets.py 03_Bot/bot.py 07_Testing/test_department_patient_ids.py relife_patch12.py")
print("git commit -m 'Use PT and DT patient IDs by department' && git push")
