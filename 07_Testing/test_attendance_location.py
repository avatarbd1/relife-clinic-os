import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "03_Bot" / "attendance_location.py"
BOT_SOURCE = (ROOT / "03_Bot" / "bot.py").read_text(encoding="utf-8")
SHEETS_SOURCE = (ROOT / "03_Bot" / "sheets.py").read_text(encoding="utf-8")
SPEC = importlib.util.spec_from_file_location("attendance_location", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AttendanceLocationTests(unittest.TestCase):
    def test_clinic_coordinate_is_inside(self):
        result = MODULE.validate_location(
            23.000000, 90.000000, 10,
            clinic_latitude=23.000000,
            clinic_longitude=90.000000,
            radius_m=200,
            max_accuracy_m=100,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "inside")

    def test_distant_coordinate_is_blocked(self):
        result = MODULE.validate_location(
            23.010000, 90.000000, 10,
            clinic_latitude=23.000000,
            clinic_longitude=90.000000,
            radius_m=200,
            max_accuracy_m=100,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "outside")

    def test_low_accuracy_is_blocked(self):
        result = MODULE.validate_location(
            23.000000, 90.000000, 150,
            clinic_latitude=23.000000,
            clinic_longitude=90.000000,
            radius_m=200,
            max_accuracy_m=100,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "low_accuracy")

    def test_missing_configuration_fails_closed(self):
        result = MODULE.validate_location(
            23.000000, 90.000000, 10,
            clinic_latitude=0,
            clinic_longitude=0,
            radius_m=200,
            max_accuracy_m=100,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "not_configured")


    def test_bot_wires_location_request_and_receiver(self):
        self.assertIn("request_location=True", BOT_SOURCE)
        self.assertIn("async def attendance_location_receive", BOT_SOURCE)
        self.assertIn("filters.LOCATION, attendance_location_receive", BOT_SOURCE)
        self.assertIn("from attendance_location import validate_location", BOT_SOURCE)

    def test_verified_location_is_written_to_attendance_note(self):
        self.assertIn('sheets.attendance_check_in, staff, location_note=audit_note', BOT_SOURCE)
        self.assertIn('await async_runtime.run_sheets_write(', BOT_SOURCE)
        self.assertIn('def attendance_check_in(staff: dict, location_note: str = "")', SHEETS_SOURCE)
        self.assertIn("        location_note,\n    ]", SHEETS_SOURCE)


if __name__ == "__main__":
    unittest.main()
