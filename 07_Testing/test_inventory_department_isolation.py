import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))

import department_access  # noqa: E402


def function(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def names(node):
    result = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        parts, current = [], item.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        result.add(".".join(reversed(parts)))
    return result


class InventoryDepartmentIsolationTests(unittest.TestCase):
    def test_inventory_reader_requires_explicit_scope(self):
        source = (BOT_DIR / "sheets.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        selected = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {
                "_department_scope_values",
                "filter_records_by_departments",
            }
        ]
        namespace = {"department_access": department_access}
        exec(compile(ast.Module(selected, []), "sheets.py", "exec"), namespace)
        rows = [
            {"Item_Name": "Gloves", "Department": "Physio"},
            {"Item_Name": "Gloves", "Department": "Dental"},
            {"Item_Name": "Unknown"},
        ]
        scoped = namespace["filter_records_by_departments"]
        self.assertEqual(
            [row["Department"] for row in scoped(rows, ["Dental"])], ["Dental"]
        )
        self.assertEqual(scoped(rows, []), [])

    def test_manual_update_reloads_staff_and_passes_department(self):
        node = function(BOT_DIR / "bot.py", "inventory_update")
        called = names(node)
        self.assertIn("_require_staff", called)
        self.assertIn("sheets.adjust_inventory_stock", called)
        source = ast.unparse(node)
        self.assertIn("department=department", source)

    def test_sheet_adjustment_is_department_keyed_and_logs_scope(self):
        node = function(BOT_DIR / "sheets.py", "adjust_inventory_stock")
        source = ast.unparse(node)
        self.assertIn("_find_inventory_row(item_name, target_department)", source)
        self.assertIn("'Department': target_department", source)

    def test_auto_deduction_receives_patient_department(self):
        node = function(BOT_DIR / "bot.py", "_treat_do_save")
        source = ast.unparse(node)
        self.assertIn('t["Department"]', source)
        self.assertIn("_apply_inventory_auto_deduct", names(node))


if __name__ == "__main__":
    unittest.main()
