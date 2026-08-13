"""চলতি হিসাব -> ক্যাশ ব্যালেন্স: new "💰 এখন কত আছে (Live)" quick view.

Reuses the already-tested get_cash_custody_summary() math over the full
record history (like get_reception_cash_balance did for Reception alone),
but now for Reception + Home Treasury + Bank together, with header/footer
wording that makes clear this is a live running balance, not a period
movement report.
"""
import os
import sys
import unittest
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("GOOGLE_SHEET_ID", "test-sheet")

_CREDENTIALS = ROOT / "credentials.json"
_CREATED_CREDENTIALS = False
if not _CREDENTIALS.exists():
    _CREDENTIALS.write_text("{}", encoding="utf-8")
    _CREATED_CREDENTIALS = True

import bot  # noqa: E402


def tearDownModule():
    if _CREATED_CREDENTIALS:
        _CREDENTIALS.unlink(missing_ok=True)


class LiveShortcutDateRangeTests(unittest.TestCase):
    def test_live_shortcut_spans_full_history_to_today(self):
        today = date(2026, 8, 14)
        start, end = bot._financial_report_date_range("live", today=today)
        self.assertEqual(start, bot._LIVE_BALANCE_START_DATE)
        self.assertEqual(end, "2026-08-14")

    def test_other_shortcuts_are_unaffected(self):
        today = date(2026, 8, 14)
        self.assertEqual(
            bot._financial_report_date_range("today", today=today),
            ("2026-08-14", "2026-08-14"),
        )


class LiveButtonKeyboardTests(unittest.TestCase):
    def test_cash_report_gets_the_live_button_first(self):
        markup = bot._financial_report_keyboard("cash")
        first_row = markup.inline_keyboard[0]
        self.assertEqual(len(first_row), 1)
        self.assertIn("Live", first_row[0].text)
        self.assertEqual(first_row[0].callback_data, "finrange_cash_live")

    def test_expense_report_has_no_live_button(self):
        markup = bot._financial_report_keyboard("expense")
        all_texts = [
            button.text
            for row in markup.inline_keyboard
            for button in row
        ]
        self.assertFalse(any("Live" in text for text in all_texts))


class LiveSummaryTextTests(unittest.TestCase):
    def _summary(self, start_date, **overrides):
        base = {
            "Date": f"{start_date} — 2026-08-14",
            "Start_Date": start_date,
            "End_Date": "2026-08-14",
            "Cash_Collected": 1000, "Reception_Expense": 200,
            "Reception_Salary": 0, "Reception_Handover": 500,
            "Reception_In_Transit": 0, "Reception_Balance": 300,
            "Home_Received": 500, "Home_Clinic_Expense": 0,
            "Home_Salary": 0, "Household_Withdrawal": 0,
            "Home_Transfer_Out": 0, "Home_In_Transit": 0, "Home_Balance": 500,
            "Bank_Received": 0, "Bank_Expense": 0, "Bank_Salary": 0,
            "Bank_Transfer_Out": 0, "Bank_Balance": 0,
            "Unclassified_Total": 0,
        }
        base.update(overrides)
        return base

    def test_live_summary_uses_live_header_and_footer(self):
        summary = self._summary(bot._LIVE_BALANCE_START_DATE)
        text = bot._cash_custody_summary_text(summary, "Owner")
        self.assertIn("এখন কত আছে (Live)", text)
        self.assertIn("বর্তমান ব্যালেন্স", text)
        self.assertNotIn("এটি নির্বাচিত সময়ের movement balance", text)

    def test_period_summary_keeps_the_old_wording(self):
        summary = self._summary("2026-08-14")
        text = bot._cash_custody_summary_text(summary, "Owner")
        self.assertIn("Cash reconciliation", text)
        self.assertIn("নির্বাচিত সময়ের net balance", text)
        self.assertIn("এটি নির্বাচিত সময়ের movement balance", text)

    def test_non_owner_still_only_sees_reception_in_live_mode(self):
        summary = self._summary(bot._LIVE_BALANCE_START_DATE)
        text = bot._cash_custody_summary_text(summary, "Receptionist")
        self.assertIn("Reception", text)
        self.assertNotIn("Home Treasury", text)
        self.assertNotIn("Bank", text)


if __name__ == "__main__":
    unittest.main()
