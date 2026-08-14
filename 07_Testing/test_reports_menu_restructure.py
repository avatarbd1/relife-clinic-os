import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


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
import config  # noqa: E402
import roles  # noqa: E402
import sheets  # noqa: E402


def tearDownModule():
    if _CREATED_CREDENTIALS:
        _CREDENTIALS.unlink(missing_ok=True)


class ReportKeyboardTests(unittest.TestCase):
    @staticmethod
    def staff(role):
        assignment = SimpleNamespace(role=SimpleNamespace(value=role))
        return {"Role": role, "_Department_Role_Assignments": (assignment,)}

    def test_owner_keeps_old_buttons_and_gets_four_finance_buttons(self):
        keyboard = bot._reports_summary_keyboard(self.staff("Owner"))
        labels = [button.text for row in keyboard.inline_keyboard for button in row]
        for label in (
            "👥 মোট রোগী ও সর্বমোট আদায়",
            "💰 গত মাসের আদায়",
            "📅 তারিখ ভিত্তিক রিপোর্ট",
            "📋 আজকের রেজিস্টার",
            "📊 এই মাসের আদায় ও খরচ",
            "📉 গত মাসের খরচ",
            "💼 ব্যবসায়িক দায়",
            "🔴 এখনও খরচ ওঠেনি",
        ):
            self.assertIn(label, labels)

    def test_non_owner_does_not_get_owner_finance_buttons(self):
        keyboard = bot._reports_summary_keyboard(self.staff("Receptionist"))
        callbacks = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]
        for callback in (
            "rpt_monthcost", "rpt_lastcost", "rpt_liability", "rpt_uncovered"
        ):
            self.assertNotIn(callback, callbacks)


class ReportSummaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_owner_summary_is_split_into_pt_and_dt_without_old_combined_block(self):
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(effective_message=message)
        context = SimpleNamespace()
        assignment = SimpleNamespace(role=SimpleNamespace(value="Owner"))
        staff = {
            "Role": "Owner",
            "_Department_Role_Assignments": (assignment,),
        }
        report_data = {
            config.SHEET_PATIENTS: [
                {"Registration_Date": "2026-08-14", "_Source_Department": "Physio"},
                {"Registration_Date": "2026-08-01", "_Source_Department": "Dental"},
            ],
            config.SHEET_PAYMENTS: [
                {"Date": "2026-08-14", "Amount": 400, "_Source_Department": "Physio"},
                {"Date": "2026-08-02", "Amount": 700, "_Source_Department": "Dental"},
            ],
        }
        current = {
            "Physio": {"Month_Clinic_Expense": 1000, "Month_Salary": 200},
            "Dental": {"Month_Clinic_Expense": 300, "Month_Salary": 50},
        }

        async def fake_read(func, *args):
            if func is sheets.get_scoped_report_records:
                return report_data
            if func is sheets.get_owner_financial_dashboard:
                return current
            raise AssertionError(func)

        with patch.object(bot, "_require_staff", AsyncMock(return_value=staff)), \
             patch.object(bot, "_staff_can_access_menu", return_value=True), \
             patch.object(bot, "_report_departments", return_value=frozenset({"All"})), \
             patch.object(bot, "bd_now", return_value=datetime(2026, 8, 14, 9, 0)), \
             patch.object(bot.async_runtime, "run_sheets_read", side_effect=fake_read), \
             patch.object(bot, "_menu_keyboard", return_value=None):
            await bot.reports_menu(update, context)

        text = message.reply_text.await_args_list[0].args[0]
        self.assertIn("🩺 Physio (PT)", text)
        self.assertIn("🦷 Dental (DT)", text)
        self.assertIn("এই মাসের আদায়: ৳400", text)
        self.assertIn("এই মাসের আদায়: ৳700", text)
        self.assertIn("এই মাসের রানিং খরচ: ৳1200", text)
        self.assertIn("এই মাসের রানিং খরচ: ৳350", text)
        self.assertNotIn("actual খরচ", text)
        self.assertNotIn("মোট ব্যবসায়িক দায়", text)
        self.assertNotIn("এখনও খরচ ওঠেনি:", text)


class FinanceDetailMathTests(unittest.TestCase):
    def test_previous_month_query_uses_last_day_not_first_day(self):
        self.assertEqual(
            bot._last_month_end_str(datetime(2026, 8, 14)),
            "2026-07-31",
        )

    def test_running_expense_and_liability_keep_existing_math(self):
        summary = {"Month_Clinic_Expense": 15460, "Month_Salary": 8650}
        self.assertEqual(bot._running_expense(summary), 24110)
        self.assertEqual(bot._business_liability(summary, 64300), 79760)

    def test_dental_liability_adds_fixed_overhead_and_variable_cost_only(self):
        summary = {
            "Month_Clinic_Expense": 16500,
            "Month_Variable_Clinic_Expense": 6500,
            "Month_Fixed_Overhead_Liability": 19000,
            "Month_Salary": 0,
        }
        self.assertEqual(bot._business_liability(summary, 23000), 48500)

    def test_finance_overview_keeps_departments_separate_and_household_outside_business(self):
        part = {
            "Month_Collection": 50000,
            "Month_Clinic_Expense": 5000,
            "Month_Variable_Clinic_Expense": 5000,
            "Month_Fixed_Overhead_Liability": 13000,
            "Month_Household_Withdrawal": 2000,
        }
        data = {
            "Date": "2026-08-14",
            "Physio": dict(part),
            "Dental": dict(part, Month_Fixed_Overhead_Liability=19000),
            "Salary_Commitment": {"Physio": 64300, "Dental": 23000},
        }
        text = bot._owner_finance_overview_text(data)
        self.assertIn("মোট PT দায়", text)
        self.assertIn("মোট DT দায়", text)
        self.assertNotIn("Combined", text)
        self.assertIn("Household — ব্যবসার হিসাব নয়", text)
        self.assertIn("এই মাসে উত্তোলন: ৳4000", text)


if __name__ == "__main__":
    unittest.main()
