import ast
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))

import physio_flow  # noqa: E402


def appointment(gender, room, bed, *, station="Treatment", status="Scheduled"):
    return {
        "Department": "Physio", "Date": "2026-08-15", "Time": "10:00 AM",
        "Status": status, "Gender": gender, "Room": room, "Bed": bed,
        "Station": station,
    }


class GenderSafeAllocationTests(unittest.TestCase):
    def test_first_patient_locks_first_room(self):
        result = physio_flow.allocate_resource([], "2026-08-15", "10:00 AM", "Female")
        self.assertEqual((result["Room"], result["Bed"]), ("Room 1", "Bed 1"))

    def test_matching_gender_fills_same_room_first(self):
        rows = [appointment("Female", "Room 1", "Bed 1")]
        result = physio_flow.allocate_resource(rows, "2026-08-15", "10:00 AM", "Female")
        self.assertEqual((result["Room"], result["Bed"]), ("Room 1", "Bed 2"))

    def test_opposite_gender_uses_other_room(self):
        rows = [appointment("Female", "Room 1", "Bed 1")]
        result = physio_flow.allocate_resource(rows, "2026-08-15", "10:00 AM", "Male")
        self.assertEqual((result["Room"], result["Bed"]), ("Room 2", "Bed 3"))

    def test_four_same_gender_patients_fit(self):
        rows = [
            appointment("Male", "Room 1", "Bed 1"),
            appointment("Male", "Room 1", "Bed 2"),
            appointment("Male", "Room 2", "Bed 3"),
        ]
        result = physio_flow.allocate_resource(rows, "2026-08-15", "10:00 AM", "Male")
        self.assertEqual((result["Room"], result["Bed"]), ("Room 2", "Bed 4"))

    def test_no_gender_compatible_fifth_bed(self):
        rows = [
            appointment("Female", "Room 1", "Bed 1"),
            appointment("Female", "Room 1", "Bed 2"),
            appointment("Male", "Room 2", "Bed 3"),
            appointment("Male", "Room 2", "Bed 4"),
        ]
        with self.assertRaises(physio_flow.PhysioCapacityError):
            physio_flow.allocate_resource(rows, "2026-08-15", "10:00 AM", "Female")

    def test_traction_has_independent_capacity_one(self):
        first = physio_flow.allocate_resource(
            [], "2026-08-15", "10:00 AM", "Male", needs_traction=True
        )
        self.assertEqual(first["Bed"], "Traction Bed")
        rows = [appointment("Male", "Traction Room", "Traction Bed", station="Traction")]
        with self.assertRaises(physio_flow.PhysioCapacityError):
            physio_flow.allocate_resource(
                rows, "2026-08-15", "10:00 AM", "Female", needs_traction=True
            )

    def test_remarks_fallback_round_trip(self):
        allocation = {"Gender": "Female", "Room": "Room 2", "Bed": "Bed 3", "Station": "Treatment"}
        remarks = physio_flow.with_flow_tag("Follow up", allocation)
        self.assertEqual(physio_flow.flow_fields({"Remarks": remarks}), allocation)

    def test_dental_and_completed_rows_do_not_consume_physio_capacity(self):
        rows = [
            {**appointment("Female", "Room 1", "Bed 1"), "Department": "Dental"},
            appointment("Female", "Room 1", "Bed 1", status="Completed"),
        ]
        result = physio_flow.allocate_resource(rows, "2026-08-15", "10:00 AM", "Male")
        self.assertEqual(result["Bed"], "Bed 1")


class QuickPlanParsingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (BOT_DIR / "bot.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        node = next(
            item for item in tree.body
            if isinstance(item, ast.FunctionDef) and item.name == "_parse_quick_protocol"
        )
        namespace = {"re": re}
        exec(ast.unparse(node), namespace)
        cls.parse = staticmethod(namespace["_parse_quick_protocol"])
        cls.source = source

    def test_one_message_populates_three_plan_fields(self):
        result = self.parse("Exercise: Core; Electro: IFT; Manual: Mobilization")
        self.assertEqual(result["Exercise_Plan"], "Core")
        self.assertEqual(result["Electrotherapy_Plan"], "IFT")
        self.assertEqual(result["Manual_Therapy_Plan"], "Mobilization")

    def test_unlabelled_protocol_is_preserved(self):
        result = self.parse("Walking and active ROM")
        self.assertEqual(result["Exercise_Plan"], "Walking and active ROM")

    def test_quick_save_explicitly_blocks_dental(self):
        function = next(
            item for item in ast.parse(self.source).body
            if isinstance(item, ast.AsyncFunctionDef) and item.name == "tplan_quick_confirm"
        )
        self.assertIn("DEPARTMENT_DENTAL", ast.unparse(function))


if __name__ == "__main__":
    unittest.main()
