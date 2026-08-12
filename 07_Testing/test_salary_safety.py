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


class SalarySafetyTests(unittest.TestCase):
    def test_sheet_money_parser_accepts_currency_and_commas(self):
        body = source(BOT_DIR / "sheets.py", "_safe_float")
        self.assertIn('replace("৳", "")', body)
        self.assertIn('replace(",", "")', body)

    def test_salary_summary_uses_safe_parser(self):
        body = source(BOT_DIR / "sheets.py", "get_salary_summary")
        self.assertNotIn("float(staff.get", body)
        self.assertNotIn("float(r.get", body)
        self.assertGreaterEqual(body.count("_safe_float"), 2)

    def test_checked_payment_reloads_due_before_append(self):
        body = source(BOT_DIR / "sheets.py", "add_salary_payment_checked")
        self.assertIn("get_salary_summary", body)
        self.assertIn("amount_exceeds_due", body)
        self.assertIn("already_paid", body)
        self.assertIn("add_salary_payment", body)

    def test_confirm_reloads_staff_and_menu_permission(self):
        body = source(BOT_DIR / "bot.py", "salary_confirm_receive")
        self.assertIn("_require_staff", body)
        self.assertIn("_staff_can_access_menu", body)
        self.assertIn("MENU_SALARY", body)
        self.assertIn("add_salary_payment_checked", body)
        self.assertNotIn('Error: {', body)


if __name__ == "__main__":
    unittest.main()
