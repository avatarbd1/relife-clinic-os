import os, sys, unittest
from pathlib import Path
from unittest.mock import patch

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


if __name__ == "__main__": unittest.main()
