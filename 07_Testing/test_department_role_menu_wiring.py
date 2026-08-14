import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("GOOGLE_SHEET_ID", "TEST_SHEET")
os.environ.setdefault("GOOGLE_CREDENTIALS_PATH", __file__)

import bot  # noqa: E402
import config  # noqa: E402
import roles  # noqa: E402
import sheets  # noqa: E402


class MultiRoleMenuTests(unittest.TestCase):
    def test_therapist_daily_clinical_menu_is_visible(self):
        rows = roles.ROLE_MENU_ROWS[roles.Role.THERAPIST]
        self.assertEqual(
            rows,
            [
                [roles.MENU_HOME],
                [roles.MENU_MY_PATIENTS],
                [roles.MENU_APPOINTMENT, roles.MENU_PATIENT_LIST],
                [roles.MENU_TREATMENT_NOTE, roles.MENU_TREATMENT_PLAN],
                [roles.MENU_PATIENT_HISTORY, roles.MENU_TREATMENT_HISTORY],
                [roles.MENU_CLINICAL_AI],
                [roles.MENU_CASE_STUDY, roles.MENU_INVENTORY],
            ],
        )

    def test_therapist_schedule_can_open_attendance_and_own_appointments(self):
        items = roles.get_menu_for_role(roles.Role.THERAPIST.value)
        self.assertIn(roles.MENU_ATTENDANCE, items)
        self.assertIn(roles.MENU_TODAY_APPOINTMENTS, items)

    def test_therapist_has_no_dental_or_finance_menu_access(self):
        items = roles.get_menu_for_role(roles.Role.THERAPIST.value)
        forbidden = {
            roles.MENU_PAYMENT,
            roles.MENU_FINANCE,
            roles.MENU_FINANCE_OVERVIEW,
            roles.MENU_CASH_HANDOVER,
            roles.MENU_DENTAL_FINANCE_DASHBOARD,
        }
        self.assertTrue(forbidden.isdisjoint(items))

    def test_manager_and_therapist_menus_are_combined_without_duplicates(self):
        items = roles.get_menu_for_roles(["Manager", "Therapist"])
        self.assertIn(roles.MENU_PATIENT_MGMT, items)
        self.assertIn(roles.MENU_MY_PATIENTS, items)
        self.assertEqual(len(items), len(set(items)))

    def test_unknown_and_unassigned_roles_grant_nothing(self):
        self.assertEqual(roles.get_menu_for_roles(["Unknown"]), [])
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            self.assertFalse(
                bot._staff_can_access_menu(
                    {"Staff_ID": "ST010", "Role": "Manager"},
                    roles.MENU_REPORTS,
                )
            )

    def test_effective_assignments_not_staff_role_drive_permission(self):
        assignment = SimpleNamespace(role=SimpleNamespace(value="Receptionist"))
        staff = {
            "Staff_ID": "ST010",
            "Role": "Manager",
            "_Department_Role_Assignments": frozenset({assignment}),
        }
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            self.assertTrue(
                bot._staff_can_access_menu(staff, roles.MENU_PAYMENT)
            )
            self.assertFalse(
                bot._staff_can_access_menu(staff, roles.MENU_TREATMENT)
            )


class RequireStaffAssignmentTests(unittest.IsolatedAsyncioTestCase):
    def _update(self):
        return SimpleNamespace(
            effective_user=SimpleNamespace(id=1810282475),
            effective_message=SimpleNamespace(reply_text=AsyncMock()),
        )

    async def test_require_staff_loads_live_department_roles(self):
        update = self._update()
        context = SimpleNamespace(user_data={})
        staff = {"Staff_ID": "ST010", "Role": "Manager"}
        mappings = [{
            "Staff_ID": "ST010",
            "Department": "Dental",
            "Role": "Manager",
            "Status": "Active",
        }]
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            bot.async_runtime, "run_role_lookup", AsyncMock(return_value=staff)
        ), patch.object(
            bot.async_runtime, "run_sheets_read", AsyncMock(return_value=mappings)
        ) as read:
            result = await bot._require_staff(update, context)

        self.assertEqual(
            bot._effective_role_strings(result), ["Manager"]
        )
        self.assertEqual(result["_Department_Mappings"], mappings)
        self.assertEqual(read.await_args.args[0], sheets.get_staff_department_access)

    async def test_bare_manager_without_mapping_fails_closed(self):
        update = self._update()
        context = SimpleNamespace(user_data={})
        staff = {"Staff_ID": "ST010", "Role": "Manager"}
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            bot.async_runtime, "run_role_lookup", AsyncMock(return_value=staff)
        ), patch.object(
            bot.async_runtime, "run_sheets_read", AsyncMock(return_value=[])
        ):
            result = await bot._require_staff(update, context)

        self.assertIsNone(result)
        update.effective_message.reply_text.assert_awaited_once()
        self.assertIn(
            "Department + Role assignment",
            update.effective_message.reply_text.await_args.args[0],
        )


if __name__ == "__main__":
    unittest.main()
