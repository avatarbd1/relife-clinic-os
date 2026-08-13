#!/usr/bin/env python3
"""Use 08_Staff as the only staff role/department source of truth.

Run from ~/relife-clinic-os:
    python3 relife_patch9.py

No patient, payment, treatment, finance, or ID data is migrated or edited.
Safe to re-run.
"""
from pathlib import Path


ROOT = Path.home() / "relife-clinic-os"
SHEETS_PY = ROOT / "03_Bot" / "sheets.py"
TEST_PY = ROOT / "07_Testing" / "test_staff_single_source.py"


OLD = '''def get_staff_department_access(staff_id: str | None = None) -> list[dict]:
    """Load active mapping rows once for a staff-scoped authorization request."""
    ws = _worksheet(config.SHEET_STAFF_DEPARTMENT_ACCESS)
    records = safe_get_all_records(ws)
    if staff_id is None:
        return records
    target = str(staff_id).strip()
    return [
        row for row in records
        if str(row.get("Staff_ID", "")).strip() == target
        and str(row.get("Status", "Active")).strip().casefold() == "active"
    ]
'''

NEW = '''def get_staff_department_access(staff_id: str | None = None) -> list[dict]:
    """Build authorization assignments only from 08_Staff.

    The function name is retained so existing callers remain stable, but the
    deleted Staff_Department_Access worksheet is never opened. Role and
    Primary_Department on the active 08_Staff row are the single source of
    truth. Invalid or blank values fail closed.
    """
    records = safe_get_all_records(_worksheet(config.SHEET_STAFF))
    target = str(staff_id or "").strip()
    assignments = []
    for row in records:
        row_staff_id = str(row.get("Staff_ID", "")).strip()
        if not row_staff_id or (target and row_staff_id != target):
            continue
        if str(row.get("Status", "")).strip().casefold() != "active":
            continue
        department = department_access.normalize_department(
            row.get("Primary_Department")
        )
        role = department_access.normalize_role(row.get("Role"))
        if department is None or role is None:
            continue
        if (
            department is department_access.Department.ALL
            and role is not department_access.Role.OWNER
        ):
            continue
        assignments.append({
            "Staff_ID": row_staff_id,
            "Department": department.value,
            "Role": role.value,
            "Status": "Active",
        })
    return assignments
'''

TEST = '''"""08_Staff is the only runtime staff department source."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("GOOGLE_SHEET_ID", "test-sheet")

CREDS = ROOT / "credentials.json"
CREATED_CREDS = False
if not CREDS.exists():
    CREDS.write_text("{}", encoding="utf-8")
    CREATED_CREDS = True

import config  # noqa: E402
import sheets  # noqa: E402


def tearDownModule():
    if CREATED_CREDS:
        CREDS.unlink(missing_ok=True)


ROWS = [
    {"Staff_ID": "ST001", "Role": "Owner", "Primary_Department": "All", "Status": "Active"},
    {"Staff_ID": "ST007", "Role": "Receptionist", "Primary_Department": "Dental", "Status": "Active"},
    {"Staff_ID": "ST008", "Role": "Receptionist", "Primary_Department": "Physio", "Status": "Active"},
    {"Staff_ID": "ST009", "Role": "Receptionist", "Primary_Department": "", "Status": "Active"},
    {"Staff_ID": "ST010", "Role": "Receptionist", "Primary_Department": "All", "Status": "Active"},
    {"Staff_ID": "ST011", "Role": "Receptionist", "Primary_Department": "Dental", "Status": "Inactive"},
]


class StaffSingleSourceTests(unittest.TestCase):
    def setUp(self):
        self.ws = object()
        self.worksheet_patch = patch.object(sheets, "_worksheet", return_value=self.ws)
        self.records_patch = patch.object(sheets, "safe_get_all_records", return_value=ROWS)
        self.mock_worksheet = self.worksheet_patch.start()
        self.records_patch.start()

    def tearDown(self):
        self.worksheet_patch.stop()
        self.records_patch.stop()

    def assignment(self, staff_id):
        return sheets.get_staff_department_access(staff_id)

    def test_avatar_is_dental_only(self):
        self.assertEqual(self.assignment("ST007"), [{
            "Staff_ID": "ST007", "Department": "Dental",
            "Role": "Receptionist", "Status": "Active",
        }])

    def test_yamoni_is_physio_only(self):
        self.assertEqual(self.assignment("ST008"), [{
            "Staff_ID": "ST008", "Department": "Physio",
            "Role": "Receptionist", "Status": "Active",
        }])

    def test_owner_all_is_valid(self):
        self.assertEqual(self.assignment("ST001")[0]["Department"], "All")

    def test_blank_invalid_all_and_inactive_fail_closed(self):
        for staff_id in ("ST009", "ST010", "ST011", "MISSING"):
            with self.subTest(staff_id=staff_id):
                self.assertEqual(self.assignment(staff_id), [])

    def test_deleted_mapping_tab_is_never_opened(self):
        self.assignment("ST007")
        self.mock_worksheet.assert_called_once_with(config.SHEET_STAFF)


if __name__ == "__main__":
    unittest.main()
'''


def stop(message: str) -> None:
    print(f"❌ {message}")
    raise SystemExit(1)


if not SHEETS_PY.exists():
    stop(f"file not found: {SHEETS_PY}")

source = SHEETS_PY.read_text(encoding="utf-8")
if NEW in source:
    print("sheets.py: ✅ already applied")
elif source.count(OLD) == 1:
    SHEETS_PY.write_text(source.replace(OLD, NEW, 1), encoding="utf-8")
    print("sheets.py: ✅ 08_Staff single-source access applied")
else:
    stop("expected get_staff_department_access() block not found uniquely; no source file changed")

TEST_PY.parent.mkdir(parents=True, exist_ok=True)
if TEST_PY.exists() and TEST_PY.read_text(encoding="utf-8") == TEST:
    print("test_staff_single_source.py: ✅ already present")
else:
    TEST_PY.write_text(TEST, encoding="utf-8")
    print("test_staff_single_source.py: ✅ created/updated")

print("\nএখন চালাও:")
print("  python3 -m py_compile 03_Bot/sheets.py")
print("  python3 -m unittest 07_Testing/test_staff_single_source.py 07_Testing/test_department_access.py -v")
print("\nTests pass হলে আগে 08_Staff-এ নিশ্চিত করো:")
print("  ST001 Primary_Department = All")
print("  ST007 Primary_Department = Dental")
print("  ST008 Primary_Department = Physio")
print("\nতারপর:")
print("  git add 03_Bot/sheets.py 07_Testing/test_staff_single_source.py relife_patch9.py")
print("  git commit -m 'Use 08 Staff as single department source' && git push")
