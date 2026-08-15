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
import sheets  # noqa: E402


class PatientQueryAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.physio_staff = {
            "Staff_ID": "S1", "Role": "Manager",
            "Primary_Department": "Physio",
        }
        self.patients = [
            {"Patient_ID": "P1", "Full_Name": "Physio", "Department": "Physio"},
            {"Patient_ID": "P2", "Full_Name": "Dental", "Department": "Dental"},
            {"Patient_ID": "P3", "Full_Name": "Missing", "Department": ""},
        ]

    def test_flag_off_preserves_legacy_rows(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", False):
            visible = sheets.filter_patients_for_staff(
                self.patients, self.physio_staff, []
            )
        self.assertIs(visible, self.patients)

    def test_flag_on_filters_mismatch_and_missing_department(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            visible = sheets.filter_patients_for_staff(
                self.patients, self.physio_staff, []
            )
        self.assertEqual([row["Patient_ID"] for row in visible], ["P1"])

    def test_physio_therapist_patient_list_excludes_dental(self):
        therapist = {
            "Staff_ID": "T1", "Role": "Therapist",
            "Primary_Department": "Physio",
        }
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            visible = sheets.filter_patients_for_staff(
                self.patients, therapist, []
            )
        self.assertEqual([row["Patient_ID"] for row in visible], ["P1"])

    def test_owner_requires_explicit_all_scope(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            allowed = sheets.filter_patients_for_staff(
                self.patients,
                {"Staff_ID": "O1", "Role": "Owner", "Primary_Department": "All"},
                [],
            )
            denied = sheets.filter_patients_for_staff(
                self.patients,
                {"Staff_ID": "O1", "Role": "Owner", "Primary_Department": ""},
                [],
            )
        self.assertEqual([row["Patient_ID"] for row in allowed], ["P1", "P2"])
        self.assertEqual(denied, [])

    def test_mapping_loader_returns_only_active_staff_assignment(self):
        # get_staff_department_access() is intentionally retained as a stable
        # function name, but 08_Staff is now the single source of truth. The
        # old Staff_Department_Access worksheet no longer drives authorization.
        rows = [
            {
                "Staff_ID": "S1",
                "Role": "Manager",
                "Primary_Department": "Physio",
                "Status": "Active",
            },
            {
                "Staff_ID": "S1",
                "Role": "Manager",
                "Primary_Department": "Dental",
                "Status": "Inactive",
            },
            {
                "Staff_ID": "S2",
                "Role": "Dentist",
                "Primary_Department": "Dental",
                "Status": "Active",
            },
        ]
        with patch.object(sheets, "_worksheet", return_value=object()), patch.object(
            sheets, "safe_get_all_records", return_value=rows
        ):
            result = sheets.get_staff_department_access("S1")
        self.assertEqual(
            result,
            [{
                "Staff_ID": "S1",
                "Department": "Physio",
                "Role": "Manager",
                "Status": "Active",
            }],
        )


class PatientHandlerAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_lookup_reloads_current_staff_and_mapping(self):
        staff = {"Staff_ID": "S1", "Role": "Manager", "Primary_Department": "Physio"}
        update, context = SimpleNamespace(), SimpleNamespace()
        run_read = AsyncMock(side_effect=[[{"Department": "Physio"}], {"Patient_ID": "P1"}])
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            bot, "_require_staff", AsyncMock(return_value=staff)
        ) as require_staff, patch.object(
            bot.async_runtime, "run_sheets_read", run_read
        ):
            patient = await bot._patient_by_id_for_request(
                update, context, "P1"
            )
        self.assertEqual(patient["Patient_ID"], "P1")
        require_staff.assert_awaited_once_with(update, context)
        self.assertEqual(run_read.await_args_list[0].args[0], sheets.get_staff_department_access)
        self.assertEqual(run_read.await_args_list[1].args[0], sheets.get_patient_by_id_for_staff)

    async def test_flag_off_does_not_read_mapping_tab(self):
        staff = {"Staff_ID": "S1", "Role": "Manager"}
        run_read = AsyncMock(return_value={"Patient_ID": "P1"})
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", False), patch.object(
            bot, "_require_staff", AsyncMock(return_value=staff)
        ), patch.object(bot.async_runtime, "run_sheets_read", run_read):
            await bot._patient_by_id_for_request(
                SimpleNamespace(), SimpleNamespace(), "P1"
            )
        self.assertEqual(run_read.await_count, 1)
        self.assertEqual(run_read.await_args.args[0], sheets.get_patient_by_id)

    async def test_stale_patient_card_is_reauthorized_not_trusted(self):
        query = SimpleNamespace(
            data="plistsel_P1_0",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(
            user_data={"plist_patients": {"P1": {"Patient_ID": "P1"}}}
        )
        with patch.object(
            bot, "_patient_by_id_for_request", AsyncMock(return_value=None)
        ):
            await bot.patient_list_select_callback(update, context)
        query.edit_message_text.assert_awaited_once()
        self.assertIn("মেয়াদ শেষ", query.edit_message_text.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
