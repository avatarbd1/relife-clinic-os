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


class AppointmentQueryAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.staff = {
            "Staff_ID": "S1", "Role": "Manager",
            "Primary_Department": "Physio",
        }
        self.appointments = [
            {"Appointment_ID": "A1", "Patient_Name": "One", "Department": "Physio"},
            {"Appointment_ID": "A2", "Patient_Name": "Two", "Department": "Dental"},
            {"Appointment_ID": "A3", "Patient_Name": "Three", "Department": ""},
        ]

    def test_flag_off_preserves_legacy_rows(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", False):
            visible = sheets.filter_appointments_for_staff(
                self.appointments, self.staff, []
            )
        self.assertIs(visible, self.appointments)

    def test_flag_on_filters_mismatch_and_missing_department(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            visible = sheets.filter_appointments_for_staff(
                self.appointments, self.staff, []
            )
        self.assertEqual([row["Appointment_ID"] for row in visible], ["A1"])

    def test_owner_requires_explicit_all_scope(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True):
            allowed = sheets.filter_appointments_for_staff(
                self.appointments,
                {"Staff_ID": "O1", "Role": "Owner", "Primary_Department": "All"},
                [],
            )
            denied = sheets.filter_appointments_for_staff(
                self.appointments,
                {"Staff_ID": "O1", "Role": "Owner", "Primary_Department": ""},
                [],
            )
        self.assertEqual(
            [row["Appointment_ID"] for row in allowed], ["A1", "A2"]
        )
        self.assertEqual(denied, [])

    def test_search_is_filtered_at_query_foundation(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            sheets, "search_appointments", return_value=self.appointments
        ):
            visible = sheets.search_appointments_for_staff("a", self.staff, [])
        self.assertEqual([row["Appointment_ID"] for row in visible], ["A1"])

    def test_direct_lookup_is_filtered_at_query_foundation(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            sheets, "get_appointment_by_id", return_value=self.appointments[1]
        ):
            result = sheets.get_appointment_by_id_for_staff("A2", self.staff, [])
        self.assertIsNone(result)

    def test_date_and_patient_lists_are_filtered(self):
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            sheets, "get_appointments_for_date", return_value=self.appointments
        ), patch.object(
            sheets, "get_appointments_for_patient", return_value=self.appointments
        ):
            by_date = sheets.get_appointments_for_date_for_staff(
                "2026-08-12", self.staff, []
            )
            by_patient = sheets.get_appointments_for_patient_for_staff(
                "P1", self.staff, []
            )
        self.assertEqual([row["Appointment_ID"] for row in by_date], ["A1"])
        self.assertEqual([row["Appointment_ID"] for row in by_patient], ["A1"])


class AppointmentHandlerAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_direct_lookup_reloads_current_staff_and_mapping(self):
        staff = {"Staff_ID": "S1", "Role": "Manager", "Primary_Department": "Physio"}
        update, context = SimpleNamespace(), SimpleNamespace()
        run_read = AsyncMock(side_effect=[[{"Department": "Physio"}], {"Appointment_ID": "A1"}])
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            bot, "_require_staff", AsyncMock(return_value=staff)
        ) as require_staff, patch.object(
            bot.async_runtime, "run_sheets_read", run_read
        ):
            appointment = await bot._appointment_by_id_for_request(
                update, context, "A1"
            )
        self.assertEqual(appointment["Appointment_ID"], "A1")
        require_staff.assert_awaited_once_with(update, context)
        self.assertEqual(run_read.await_args_list[0].args[0], sheets.get_staff_department_access)
        self.assertEqual(run_read.await_args_list[1].args[0], sheets.get_appointment_by_id_for_staff)

    async def test_flag_off_direct_lookup_preserves_legacy_path(self):
        run_read = AsyncMock(return_value={"Appointment_ID": "A1"})
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", False), patch.object(
            bot, "_require_staff", AsyncMock()
        ) as require_staff, patch.object(bot.async_runtime, "run_sheets_read", run_read):
            await bot._appointment_by_id_for_request(
                SimpleNamespace(), SimpleNamespace(), "A1"
            )
        require_staff.assert_not_awaited()
        self.assertEqual(run_read.await_args.args[0], sheets.get_appointment_by_id)

    async def test_stale_status_callback_is_denied_before_write(self):
        query = SimpleNamespace(
            data="aptstatus_A2_Completed_P2",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            bot, "_appointment_by_id_for_request", AsyncMock(return_value=None)
        ), patch.object(
            bot.async_runtime, "run_sheets_write", AsyncMock()
        ) as run_write:
            await bot.apt_status_callback(update, SimpleNamespace())
        run_write.assert_not_awaited()
        self.assertIn("অনুমতি নেই", query.edit_message_text.await_args.args[0])

    async def test_today_list_uses_authorized_query_when_enabled(self):
        staff = {"Staff_ID": "S1", "Role": "Owner", "Primary_Department": "All"}
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(message=message, effective_message=message)
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            bot, "_require_staff", AsyncMock(return_value=staff)
        ), patch.object(
            bot, "_appointments_for_date_for_request", AsyncMock(return_value=[])
        ) as visible_date:
            await bot.today_appointments(update, SimpleNamespace())
        visible_date.assert_awaited_once()

    async def test_dashboard_receive_reauthorizes_appointment_before_patient(self):
        query = SimpleNamespace(
            data="ptrecv_A2_P2", answer=AsyncMock(), edit_message_text=AsyncMock()
        )
        update = SimpleNamespace(callback_query=query)
        with patch.object(config, "DEPARTMENT_ENFORCEMENT_ENABLED", True), patch.object(
            bot, "_appointment_by_id_for_request", AsyncMock(return_value=None)
        ), patch.object(
            bot, "_patient_by_id_for_request", AsyncMock()
        ) as patient_lookup:
            result = await bot.pt_dashboard_receive_callback(update, SimpleNamespace())
        patient_lookup.assert_not_awaited()
        self.assertEqual(result, bot.ConversationHandler.END)


if __name__ == "__main__":
    unittest.main()
