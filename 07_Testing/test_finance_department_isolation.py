import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))


def function(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def source(path, name):
    return ast.unparse(function(path, name))


class FinanceDepartmentIsolationTests(unittest.TestCase):
    def test_finance_reads_accept_explicit_departments(self):
        path = BOT_DIR / "sheets.py"
        for name in [
            "get_expense_requests",
            "get_expenses_for_date",
            "get_cash_custody_summary",
            "get_cash_movements_for_date",
            "get_pending_cash_movements",
        ]:
            with self.subTest(name=name):
                args = [arg.arg for arg in function(path, name).args.args]
                self.assertIn("departments", args)

    def test_finalizers_repeat_department_guard(self):
        path = BOT_DIR / "sheets.py"
        for name in [
            "_finalize_expense_status",
            "finalize_expense_request",
            "mark_expense_paid",
            "finalize_cash_movement",
        ]:
            with self.subTest(name=name):
                self.assertIn("departments", source(path, name))
        self.assertIn("department_forbidden", source(path, "_finalize_expense_status"))
        self.assertIn("department_forbidden", source(path, "finalize_cash_movement"))

    def test_expense_public_finalizers_forward_department_scope(self):
        path = BOT_DIR / "sheets.py"
        for name in ["finalize_expense_request", "mark_expense_paid"]:
            with self.subTest(name=name):
                fn_source = source(path, name)
                self.assertIn("departments", fn_source)
                self.assertIn("_finalize_expense_status", fn_source)
                call = next(
                    node for node in ast.walk(function(path, name))
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_finalize_expense_status"
                )
                self.assertTrue(
                    any(
                        isinstance(arg, ast.Name) and arg.id == "departments"
                        for arg in call.args
                    )
                )

    def test_bot_lists_and_reports_pass_current_scope(self):
        path = BOT_DIR / "bot.py"
        for name in [
            "cash_receive_start",
            "cash_movements_start",
            "expense_approval_start",
            "approved_expenses_start",
            "_show_financial_report",
        ]:
            with self.subTest(name=name):
                self.assertIn("_finance_departments(staff)", source(path, name))

    def test_stale_finance_callbacks_reload_staff(self):
        path = BOT_DIR / "bot.py"
        for name in [
            "cash_finalize_callback",
            "expense_approval_callback",
            "expense_paid_callback",
            "cash_department_callback",
            "cost_department_callback",
        ]:
            with self.subTest(name=name):
                self.assertIn("_require_staff", source(path, name))

    def test_finance_views_tolerate_formatted_sheet_amounts(self):
        path = BOT_DIR / "bot.py"
        helper = source(path, "_sheet_amount_value")
        self.assertIn('replace("৳", "")', helper)
        self.assertIn('replace(",", "")', helper)
        self.assertIn("except (TypeError, ValueError)", helper)
        for name in [
            "reports_menu",
            "rpt_totals_callback",
            "rpt_lastmonth_callback",
            "cash_receive_start",
            "cash_movements_start",
            "expense_approval_start",
            "approved_expenses_start",
            "_expense_report_text",
        ]:
            with self.subTest(name=name):
                body = source(path, name)
                self.assertNotIn("float(row.get('Amount'", body)
                self.assertNotIn('float(row.get("Amount"', body)
                self.assertNotIn('float(p.get("Amount"', body)

    def test_final_expense_and_cash_creation_recheck_selected_department(self):
        path = BOT_DIR / "bot.py"
        self.assertIn("_staff_has_finance_department", source(path, "cost_confirm_receive"))
        self.assertIn("_staff_has_finance_department", source(path, "cash_confirm_receive"))


if __name__ == "__main__":
    unittest.main()
