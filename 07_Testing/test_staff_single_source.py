"""08_Staff is the only runtime staff department source."""
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
