import ast
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SHEETS_PATH = ROOT / "03_Bot" / "sheets.py"
TREE = ast.parse(SHEETS_PATH.read_text(encoding="utf-8"))


def load_attendance_check_in(overrides):
    function = next(
        node for node in TREE.body
        if isinstance(node, ast.FunctionDef) and node.name == "attendance_check_in"
    )
    namespace = {
        "bd_now": lambda: datetime(2026, 8, 10, 9, 15),
        "config": SimpleNamespace(SHEET_ATTENDANCE="03_Attendance"),
        **overrides,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SHEETS_PATH), "exec"), namespace)
    return namespace["attendance_check_in"]


class AttendanceIntegrityTests(unittest.TestCase):
    def test_duplicate_check_in_returns_existing_time_without_appending(self):
        calls = {"worksheet": 0, "next_id": 0, "append": 0}

        def forbidden(name):
            def call(*args, **kwargs):
                calls[name] += 1
                raise AssertionError(f"duplicate Check-In must not call {name}")
            return call

        check_in = load_attendance_check_in({
            "get_today_attendance": lambda staff_id, date: {"Check_In": "09:02 AM"},
            "_worksheet": forbidden("worksheet"),
            "_next_attendance_id": forbidden("next_id"),
            "_append_unified_row": forbidden("append"),
        })

        result = check_in({"Staff_ID": "ST001", "Full_Name": "Staff"})

        self.assertEqual(result, "09:02 AM")
        self.assertEqual(calls, {"worksheet": 0, "next_id": 0, "append": 0})

    def test_first_check_in_still_appends_one_row(self):
        appended = []
        check_in = load_attendance_check_in({
            "get_today_attendance": lambda staff_id, date: None,
            "_worksheet": lambda name: object(),
            "_next_attendance_id": lambda ws: "AT0001",
            "_append_unified_row": lambda *args, **kwargs: appended.append((args, kwargs)),
        })

        result = check_in({"Staff_ID": "ST001", "Full_Name": "Staff", "Role": "Therapist"})

        self.assertEqual(result, "09:15 AM")
        self.assertEqual(len(appended), 1)
        self.assertEqual(appended[0][0][1][0], "AT0001")


if __name__ == "__main__":
    unittest.main()
