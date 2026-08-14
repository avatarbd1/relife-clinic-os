import os, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))
os.environ.setdefault("BOT_TOKEN", "test")
os.environ.setdefault("GOOGLE_SHEET_ID", "physio")
os.environ.setdefault("DENTAL_GOOGLE_SHEET_ID", "dental")
credentials = ROOT / "credentials.json"
if not credentials.exists(): credentials.write_text("{}", encoding="utf-8")

import bot, sheets


class DentalPaymentFlowTests(unittest.TestCase):
    def test_dental_register_does_not_increase_session_total(self):
        payments=[{"Department":"Dental","Date":"2026-08-14","Remarks":"Service: Filling | REQ:1",
                   "Amount":500,"Due":0,"Patient_Name":"Esmail","SL":1}]
        with patch.object(sheets, "get_all_payments", return_value=payments):
            result=sheets.get_daily_register("2026-08-14", {"Dental"})
        self.assertEqual(result["total_sessions"], 0)
        self.assertEqual(result["rows"][0]["Service"], "Filling")

    def test_finance_amount_stays_in_normal_amount_column(self):
        captured={}
        with patch.object(sheets, "_worksheet"), patch.object(sheets, "_next_receipt_no", return_value="RC1"), patch.object(
            sheets, "_next_daily_sl", return_value=1
        ), patch.object(sheets, "_append_unified_row", side_effect=lambda ws,row,*a,**k:captured.setdefault("row",row)):
            sheets.add_payment({"Patient_ID":"DT1","Patient_Name":"A","Department":"Dental",
                "Amount":500,"Payment_Method":"Cash","Remarks":"Service: Filling"})
        self.assertEqual(captured["row"][6], 500)
        self.assertEqual(captured["row"][11], "Service: Filling")

    def test_dental_service_keyboard_has_no_session_buttons(self):
        labels=[button.text for row in bot._dental_service_keyboard().keyboard for button in row]
        self.assertIn("Filling", labels)
        self.assertIn("RCT", labels)
        self.assertFalse(any("সেশন" in label for label in labels))


class DentalPatientListPaymentTests(unittest.IsolatedAsyncioTestCase):
    async def test_patient_list_payment_asks_for_dental_service_not_sessions(self):
        patient = {
            "Patient_ID": "DT0002",
            "Full_Name": "Rimon",
            "Department": "Dental",
        }
        query = SimpleNamespace(
            data="plistact_pay_DT0002",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={})

        with patch.object(
            bot,
            "_authorized_patient_action",
            AsyncMock(return_value=({"Role": "Receptionist"}, patient)),
        ):
            state = await bot.plist_action_pay(update, context)

        self.assertEqual(state, bot.PAY_SESSION)
        self.assertEqual(context.user_data["payment"]["Sessions"], 0)
        prompt = query.message.reply_text.await_args.args[0]
        self.assertIn("Dental service/procedure", prompt)
        self.assertNotIn("কত টাকা নেওয়া হলো", prompt)


if __name__ == "__main__": unittest.main()
