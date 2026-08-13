import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("GOOGLE_SHEET_ID", "physio")
os.environ.setdefault("DENTAL_GOOGLE_SHEET_ID", "dental")
credentials = ROOT / "credentials.json"
created = False
if not credentials.exists():
    credentials.write_text("{}", encoding="utf-8")
    created = True

import bot
import config
import sheets


def tearDownModule():
    if created:
        credentials.unlink(missing_ok=True)


class DentalClinicalStage3Tests(unittest.IsolatedAsyncioTestCase):
    async def test_dental_patient_enters_procedure_flow_without_physio_plan(self):
        query = SimpleNamespace(
            data="treatsel_DT0001", answer=AsyncMock(), edit_message_text=AsyncMock(),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={"treatment": {}, "treat_selected": set()})
        patient = {"Patient_ID": "DT0001", "Full_Name": "Dental One", "Department": "Dental"}
        with patch.object(bot, "_patient_by_id_for_request", AsyncMock(return_value=patient)), patch.object(
            bot, "_treat_prepare_for_patient", AsyncMock()
        ) as physio_prepare:
            state = await bot.treat_select_callback(update, context)
        self.assertEqual(state, bot.DENTAL_PROCEDURE)
        self.assertEqual(context.user_data["dental_treatment"]["Patient_ID"], "DT0001")
        physio_prepare.assert_not_awaited()

    async def test_dental_save_writes_one_note_without_session_or_inventory_updates(self):
        message = SimpleNamespace(text="হ্যাঁ", reply_text=AsyncMock())
        update = SimpleNamespace(message=message, effective_message=message)
        data = {
            "Patient_ID": "DT0001", "Patient_Name": "Dental One",
            "Procedure": "Filling", "Tooth_Area": "16",
            "Clinical_Note": "Caries removed and restored", "Status": "Completed",
        }
        context = SimpleNamespace(user_data={"dental_treatment": data})
        staff = {"Full_Name": "Dr Test"}
        patient = {"Patient_ID": "DT0001", "Full_Name": "Dental One", "Department": "Dental"}
        async def run_write(func, *args, **kwargs):
            return func(*args, **kwargs)
        with patch.object(bot, "_authorized_patient_action", AsyncMock(return_value=(staff, patient))), patch.object(
            bot.async_runtime, "run_sheets_write", side_effect=run_write
        ), patch.object(sheets, "add_treatment_note", return_value="TR0001") as add_note, patch.object(
            sheets, "increment_plan_session"
        ) as increment, patch.object(bot, "_apply_inventory_auto_deduct") as inventory:
            state = await bot.dental_confirm_receive(update, context)
        self.assertEqual(state, bot.ConversationHandler.END)
        payload = add_note.call_args.args[0]
        self.assertEqual(payload["Department"], "Dental")
        self.assertEqual(payload["Treatment_Given"], "Filling")
        self.assertNotIn("Session_No", payload)
        increment.assert_not_called()
        inventory.assert_not_called()

    async def test_dental_treatment_plan_is_blocked(self):
        query = SimpleNamespace(
            data="tplansel_DT0001", answer=AsyncMock(), edit_message_text=AsyncMock(),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={})
        patient = {"Patient_ID": "DT0001", "Full_Name": "Dental One", "Department": "Dental"}
        with patch.object(bot, "_patient_by_id_for_request", AsyncMock(return_value=patient)), patch.object(
            sheets, "get_active_plan_for_patient"
        ) as active_plan:
            state = await bot.tplan_select_callback(update, context)
        self.assertEqual(state, bot.ConversationHandler.END)
        active_plan.assert_not_called()
        self.assertIn("Physio session-based", query.edit_message_text.await_args.args[0])

    async def test_dental_history_has_no_physio_fields(self):
        note = {
            "Treatment_ID": "TR0001", "Patient_ID": "DT0001", "Patient_Name": "Dental One",
            "Department": "Dental", "Date": "2026-08-14", "Treatment_Given": "Filling",
            "Clinical_Note": "Restoration done", "Remarks": "Tooth/Area: 16 | Status: Completed",
        }
        query = SimpleNamespace(edit_message_text=AsyncMock())
        context = SimpleNamespace(user_data={
            "thist_notes": {"TR0001": note}, "thist_notes_order": ["TR0001"], "staff": {},
        })
        with patch.object(bot, "_patient_card_keyboard", return_value=SimpleNamespace(inline_keyboard=[])):
            await bot._thist_render_note(query, context, "TR0001")
        text = query.edit_message_text.await_args.args[0]
        self.assertIn("Dental visit 1/1", text)
        self.assertIn("Procedure: Filling", text)
        self.assertNotIn("Exercise:", text)
        self.assertNotIn("Machines:", text)


if __name__ == "__main__":
    unittest.main()
