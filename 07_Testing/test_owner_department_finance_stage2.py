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


def tearDownModule():
    if created:
        credentials.unlink(missing_ok=True)


class OwnerFinanceSelectorStage2Tests(unittest.IsolatedAsyncioTestCase):
    def test_salary_staff_list_is_limited_to_selected_department(self):
        rows = [
            {"Staff_ID": "ST001", "Role": "Owner", "Primary_Department": "All"},
            {"Staff_ID": "ST007", "Role": "Receptionist", "Primary_Department": "Dental"},
            {"Staff_ID": "ST008", "Role": "Receptionist", "Primary_Department": "Physio"},
        ]
        dental = bot._staff_rows_for_department(
            rows, {"_Selected_Department": config.DEPARTMENT_DENTAL}
        )
        self.assertEqual([row["Staff_ID"] for row in dental], ["ST001", "ST007"])

    def test_finance_actions_have_two_department_choices(self):
        for action in (
            "salary", "salaryhist", "inventory", "cashreceive", "cashmoves",
            "expenseapproval", "approved", "cashreport", "expensereport", "rejected",
        ):
            keyboard = bot._owner_department_keyboard(action)
            callbacks = [row[0].callback_data for row in keyboard.inline_keyboard]
            self.assertEqual(callbacks, [
                f"ownerdept:{action}:Physio", f"ownerdept:{action}:Dental"
            ])

    async def test_owner_expense_department_binds_the_selected_workbook(self):
        query = SimpleNamespace(
            data="costdept_Dental", answer=AsyncMock(), edit_message_text=AsyncMock(),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={"cost": {"Mode": "owner_clinic"}})
        owner = {"Role": "Owner", "_Selected_Department": "Dental"}
        with patch.object(bot, "_require_staff", AsyncMock(return_value=owner)), patch.object(
            bot, "_staff_has_finance_department", return_value=True
        ), patch.object(bot.sheet_scope, "bind_sheet") as bind, patch.object(
            bot, "_send_expense_category_prompt", AsyncMock()
        ):
            state = await bot.cost_department_callback(update, context)
        self.assertEqual(state, bot.COST_CATEGORY)
        self.assertEqual(context.user_data["cost"]["Department"], "Dental")
        self.assertEqual(context.user_data["_owner_department"], "Dental")
        bind.assert_called_once_with("dental")


if __name__ == "__main__":
    unittest.main()
