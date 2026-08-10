import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "03_Bot" / "attendance_location.py"
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


if __name__ == "__main__":
    unittest.main()
