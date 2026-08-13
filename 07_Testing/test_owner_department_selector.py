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


class OwnerDepartmentSelectorTests(unittest.IsolatedAsyncioTestCase):
    def test_keyboard_has_explicit_physio_and_dental_callbacks(self):
        keyboard = bot._owner_department_keyboard("pay")
        buttons = [row[0] for row in keyboard.inline_keyboard]
        self.assertEqual([b.text for b in buttons], ["🩺 Physio (PT)", "🦷 Dental (DT)"])
        self.assertEqual(
            [b.callback_data for b in buttons],
            ["ownerdept:pay:Physio", "ownerdept:pay:Dental"],
        )

    def test_selected_department_replaces_owner_all_scope(self):
        staff = {
            "_Selected_Department": config.DEPARTMENT_DENTAL,
            "_Department_Role_Assignments": [],
        }
        self.assertEqual(bot._report_departments(staff), frozenset({"Dental"}))

    async def test_selection_persists_and_binds_the_matching_sheet(self):
        query = SimpleNamespace(
            data="ownerdept:pay:Dental",
            answer=AsyncMock(),
            edit_message_text=AsyncMock(),
            message=SimpleNamespace(reply_text=AsyncMock()),
        )
        update = SimpleNamespace(callback_query=query)
        context = SimpleNamespace(user_data={})
        with patch.object(bot.sheet_scope, "bind_sheet") as bind:
            selected = await bot._select_owner_department(update, context)
        self.assertEqual(selected, "Dental")
        self.assertEqual(context.user_data["_owner_department"], "Dental")
        bind.assert_called_once_with("dental")

    async def test_non_owner_is_not_prompted(self):
        update = SimpleNamespace(callback_query=None)
        context = SimpleNamespace(user_data={})
        prompted = await bot._prompt_owner_department(
            update, context, {"Role": "Receptionist"}, "pay"
        )
        self.assertFalse(prompted)


if __name__ == "__main__":
    unittest.main()
