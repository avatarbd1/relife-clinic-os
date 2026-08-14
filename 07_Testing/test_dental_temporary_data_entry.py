import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("GOOGLE_SHEET_ID", "TEST_SHEET")
os.environ.setdefault("GOOGLE_CREDENTIALS_PATH", __file__)

import bot  # noqa: E402
import config  # noqa: E402
import roles  # noqa: E402


def assignment(role, department="Dental"):
    return SimpleNamespace(
        role=SimpleNamespace(value=role),
        department=SimpleNamespace(value=department),
    )


class DentalTemporaryDataEntryMenuTests(unittest.TestCase):
    def test_dentist_has_normal_dental_clinical_menu(self):
        items = roles.get_menu_for_role("Dentist")
        for item in (
            roles.MENU_PATIENT_LIST,
            roles.MENU_APPOINTMENT,
            roles.MENU_TREATMENT_NOTE,
            roles.MENU_TREATMENT_HISTORY,
            roles.MENU_PATIENT_HISTORY,
        ):
            self.assertIn(item, items)
        self.assertNotIn(roles.MENU_FINANCE, items)

    def test_temporary_receptionist_keeps_role_and_gets_operational_buttons(self):
        staff = {
            "Staff_ID": "ST002",
            "Role": "Receptionist",
            "Clinical_Write_Scope": "Dental_Temporary_Data_Entry",
            "_Department_Role_Assignments": (assignment("Receptionist"),),
        }
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            self.assertEqual(bot._effective_role_strings(staff), ["Receptionist"])
            for item in roles.DENTAL_TEMP_DATA_ENTRY_ITEMS:
                self.assertTrue(bot._staff_can_access_menu(staff, item), item)

    def test_temporary_switch_fails_closed_for_physio_or_mixed_scope(self):
        physio = {
            "Clinical_Write_Scope": "Dental_Temporary_Data_Entry",
            "_Department_Role_Assignments": (assignment("Receptionist", "Physio"),),
        }
        mixed = {
            "Clinical_Write_Scope": "Dental_Temporary_Data_Entry",
            "_Department_Role_Assignments": (
                assignment("Receptionist", "Dental"),
                assignment("Receptionist", "Physio"),
            ),
        }
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            self.assertFalse(bot._has_temporary_dental_data_entry(physio))
            self.assertFalse(bot._has_temporary_dental_data_entry(mixed))


if __name__ == "__main__":
    unittest.main()
