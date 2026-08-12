import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "03_Bot" / "bot.py"


def source(name):
    tree = ast.parse(BOT.read_text(encoding="utf-8"))
    node = next(
        item for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        and item.name == name
    )
    return ast.unparse(node)


class EnforcementOffFinanceFallbackTests(unittest.TestCase):
    def test_report_scope_returns_all_when_enforcement_is_disabled(self):
        body = source("_report_departments")
        self.assertIn("DEPARTMENT_ENFORCEMENT_ENABLED", body)
        self.assertIn("DEPARTMENT_ALL", body)

    def test_finance_scope_and_keyboard_share_report_fallback(self):
        self.assertIn("_report_departments(staff)", source("_finance_departments"))
        body = source("_finance_department_keyboard")
        self.assertIn("_staff_has_finance_department", body)
        self.assertIn("Physio", body)
        self.assertIn("Dental", body)


if __name__ == "__main__":
    unittest.main()
