"""Guards against silent dead-ends in the finance conversation flows.

Covers the failure chain seen in production: an empty department scope produced
an inline keyboard with zero buttons, the user typed the department name, the
callback-only state let the text fall through to the global unknown-text
fallback, and the bot claimed the feature was inactive.
"""
import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "03_Bot" / "bot.py"
SHEETS = ROOT / "03_Bot" / "sheets.py"

BOT_SOURCE = BOT.read_text(encoding="utf-8")
SHEETS_SOURCE = SHEETS.read_text(encoding="utf-8")


def source(text, name):
    tree = ast.parse(text)
    node = next(
        item for item in ast.walk(tree)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == name
    )
    return ast.unparse(node)


class EmptyKeyboardTests(unittest.TestCase):
    def test_keyboard_returns_none_instead_of_an_empty_markup(self):
        body = source(BOT_SOURCE, "_finance_department_keyboard")
        self.assertIn("if not rows:", body)
        self.assertIn("return None", body)

    def test_expense_prompt_stops_when_no_department_is_available(self):
        body = source(BOT_SOURCE, "_expense_form_start")
        self.assertIn("_NO_DEPARTMENT_ACCESS_TEXT", body)
        self.assertIn("ConversationHandler.END", body)

    def test_cash_handover_prompt_stops_when_no_department_is_available(self):
        body = source(BOT_SOURCE, "cash_handover_start")
        self.assertIn("_NO_DEPARTMENT_ACCESS_TEXT", body)
        self.assertIn("ConversationHandler.END", body)

    def test_no_department_message_names_the_mapping_tab(self):
        self.assertIn("Staff_Department_Access", BOT_SOURCE)
        self.assertIn("_NO_DEPARTMENT_ACCESS_TEXT = (", BOT_SOURCE)


class TypedTextInCallbackStatesTests(unittest.TestCase):
    """Each callback-only step must answer typed text itself."""

    CALLBACK_ONLY_STATES = (
        "COST_DEPARTMENT",
        "COST_CATEGORY",
        "CASH_DEPARTMENT",
    )

    def test_states_register_a_text_handler(self):
        for state in self.CALLBACK_ONLY_STATES:
            with self.subTest(state=state):
                start = BOT_SOURCE.index(f"{state}: [")
                block = BOT_SOURCE[start:BOT_SOURCE.index("],", start)]
                self.assertIn("MessageHandler", block)
                self.assertIn("_tap_the_button", block)

    def test_tap_helper_points_the_user_at_the_buttons(self):
        body = source(BOT_SOURCE, "_tap_the_button")
        self.assertIn("বাটন", body)


class FallbackCopyTests(unittest.TestCase):
    def test_unknown_text_no_longer_claims_a_feature_is_inactive(self):
        self.assertNotIn("এই সুবিধাটি এখনো সক্রিয় করা হয়নি", BOT_SOURCE)

    def test_unknown_menu_asks_the_user_to_use_the_menu(self):
        body = source(BOT_SOURCE, "unknown_menu")
        self.assertIn("বুঝতে পারিনি", body)


class FinalizerFailureCopyTests(unittest.TestCase):
    """A permission outcome must not be reported as a missing record."""

    def test_expense_finalizers_handle_department_forbidden(self):
        for name in ("expense_approval_callback", "expense_paid_callback"):
            with self.subTest(handler=name):
                body = source(BOT_SOURCE, name)
                self.assertIn("department_forbidden", body)
                self.assertNotIn(
                    'department_forbidden"\n    else',
                    body,
                    "forbidden must have its own branch",
                )

    def test_cash_movement_finalizer_handles_department_forbidden(self):
        body = source(BOT_SOURCE, "cash_finalize_callback")
        self.assertIn("department_forbidden", body)


class SchemaGuardTests(unittest.TestCase):
    def test_expense_header_guard_covers_the_id_column(self):
        body = source(SHEETS_SOURCE, "_require_expense_workflow_headers")
        self.assertIn("Expense_ID", body)

    def test_cash_movement_finalizer_guards_its_id_column(self):
        body = source(SHEETS_SOURCE, "finalize_cash_movement")
        self.assertIn("Movement_ID", body)


if __name__ == "__main__":
    unittest.main()
