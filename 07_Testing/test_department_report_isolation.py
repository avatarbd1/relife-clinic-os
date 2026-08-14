import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))

import department_access  # noqa: E402


def _function_node(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _call_names(node) -> set[str]:
    names = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        if isinstance(item.func, ast.Name):
            names.add(item.func.id)
        elif isinstance(item.func, ast.Attribute):
            parts = []
            current = item.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            names.add(".".join(reversed(parts)))
    return names


class DepartmentReportIsolationTests(unittest.TestCase):
    def test_filter_is_department_scoped_and_missing_department_fails_closed(self):
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
        exec(compile(ast.Module(body=selected, type_ignores=[]), "sheets.py", "exec"), namespace)
        rows = [
            {"Patient_ID": "P1", "Department": "Physio"},
            {"Patient_ID": "P2", "Department": "Dental"},
            {"Patient_ID": "P3", "Department": ""},
            {"Patient_ID": "P4", "Department": "Unknown"},
        ]
        scoped = namespace["filter_records_by_departments"]
        self.assertEqual([r["Patient_ID"] for r in scoped(rows, ["Dental"])], ["P2"])
        self.assertEqual(
            [r["Patient_ID"] for r in scoped(rows, ["All"])], ["P1", "P2"]
        )
        self.assertEqual(scoped(rows, []), [])

    def test_every_report_callback_reloads_staff(self):
        path = BOT_DIR / "bot.py"
        callbacks = [
            "rpt_totals_callback",
            "rpt_lastmonth_callback",
            "rpt_daterep_callback",
            "rpt_todayregister_callback",
            "rpt_owner_finance_detail_callback",
            "date_report_calendar_navigate",
            "date_report_day_selected",
        ]
        for name in callbacks:
            with self.subTest(name=name):
                self.assertIn("_require_staff", _call_names(_function_node(path, name)))

    def test_report_reads_use_scoped_sheet_functions(self):
        path = BOT_DIR / "bot.py"
        for name in ["reports_menu", "rpt_totals_callback", "rpt_lastmonth_callback"]:
            with self.subTest(name=name):
                self.assertIn(
                    "sheets.get_scoped_report_records",
                    _call_names(_function_node(path, name)),
                )
        self.assertIn(
            "sheets.get_daily_patient_list",
            _call_names(_function_node(path, "date_report_day_selected")),
        )
        self.assertIn(
            "_report_departments",
            _call_names(_function_node(path, "date_report_day_selected")),
        )


if __name__ == "__main__":
    unittest.main()
