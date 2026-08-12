import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))


def _function(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def _qualified_call(node: ast.Call) -> str:
    parts = []
    current = node.func
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def _calls(node):
    return [
        (_qualified_call(item), getattr(item, "lineno", 0))
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
    ]


class AppointmentDepartmentIsolationTests(unittest.TestCase):
    def test_today_list_uses_scoped_query(self):
        names = {name for name, _ in _calls(_function(BOT_DIR / "bot.py", "today_appointments"))}
        self.assertIn("_require_staff", names)
        self.assertIn("sheets.get_appointments_for_date_for_staff", names)
        self.assertNotIn("sheets.get_appointments_for_date", names)

    def test_status_callback_authorizes_before_final_write(self):
        calls = _calls(_function(BOT_DIR / "bot.py", "apt_status_callback"))
        positions = {name: line for name, line in calls}
        self.assertIn("_require_staff", positions)
        self.assertIn("sheets.get_appointment_by_id_for_staff", positions)
        self.assertIn("sheets.update_appointment_status_for_staff", positions)
        self.assertNotIn("sheets.update_appointment_status", positions)
        self.assertLess(
            positions["sheets.get_appointment_by_id_for_staff"],
            positions["sheets.update_appointment_status_for_staff"],
        )

    def test_back_callback_reloads_and_reauthorizes_record(self):
        names = {name for name, _ in _calls(_function(BOT_DIR / "bot.py", "apt_today_back_callback"))}
        self.assertIn("_require_staff", names)
        self.assertIn("sheets.get_appointment_by_id_for_staff", names)
        self.assertNotIn("sheets.get_appointment_by_id", names)

    def test_sheet_final_write_repeats_record_authorization(self):
        names = {
            name for name, _ in _calls(
                _function(BOT_DIR / "sheets.py", "update_appointment_status_for_staff")
            )
        }
        self.assertIn("get_appointment_by_id_for_staff", names)
        self.assertIn("update_appointment_status", names)


if __name__ == "__main__":
    unittest.main()
