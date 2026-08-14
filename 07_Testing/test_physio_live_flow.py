import ast
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


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

    def test_fast_multiline_entry_separates_electro_and_manual(self):
        result = self.parse(
            "Shoulder elevation.\n\nEMS\nDeltoid teres minor biceps triceps releasing"
        )
        self.assertEqual(result["Exercise_Plan"], "Shoulder elevation.")
        self.assertEqual(result["Electrotherapy_Plan"], "EMS")
        self.assertEqual(
            result["Manual_Therapy_Plan"],
            "Deltoid teres minor biceps triceps releasing",
        )

    def test_repeated_label_lines_are_not_lost(self):
        result = self.parse("Manual: Release\nManual: Mobilization")
        self.assertEqual(result["Manual_Therapy_Plan"], "Release\nMobilization")

    def test_quick_save_explicitly_blocks_dental(self):
        function = next(
            item for item in ast.parse(self.source).body
            if isinstance(item, ast.AsyncFunctionDef) and item.name == "tplan_quick_confirm"
        )
        self.assertIn("DEPARTMENT_DENTAL", ast.unparse(function))

    def test_quick_session_choices_are_clear(self):
        for label in ("৭ সেশন", "১৪ সেশন", "২১ সেশন", "২৮ সেশন"):
            self.assertIn(label, self.source)

    def test_quick_plan_requires_review_and_has_field_edits(self):
        for callback in (
            "qpedit_exercise", "qpedit_electro", "qpedit_manual",
            "qpedit_finding", "qpedit_sessions", "qpsave", "qpcancel",
        ):
            self.assertIn(callback, self.source)


class MissingGenderCaptureTests(unittest.TestCase):
    def _load_writer(self, patient, worksheet=None):
        source = (BOT_DIR / "sheets.py").read_text(encoding="utf-8")
        function = next(
            item for item in ast.parse(source).body
            if isinstance(item, ast.FunctionDef)
            and item.name == "set_missing_patient_gender_for_staff"
        )
        ws = worksheet or Mock()
        namespace = {
            "physio_flow": physio_flow,
            "get_patient_by_id_for_staff": Mock(return_value=patient),
            "_worksheet": Mock(return_value=ws),
            "_invalidate_cache": Mock(),
            "config": SimpleNamespace(SHEET_PATIENTS="02_Patients"),
        }
        exec(ast.unparse(function), namespace)
        return namespace["set_missing_patient_gender_for_staff"], ws

    def test_missing_gender_is_written_by_header(self):
        ws = Mock()
        ws.row_values.return_value = ["Patient_ID", "Full_Name", "Gender"]
        ws.find.return_value = SimpleNamespace(row=4)
        writer, _ = self._load_writer(
            {"Patient_ID": "PT1", "Gender": ""}, ws
        )
        self.assertTrue(writer("PT1", "Female", {}, []))
        ws.update_cell.assert_called_once_with(4, 3, "Female")

    def test_existing_gender_is_never_overwritten(self):
        writer, ws = self._load_writer({"Patient_ID": "PT1", "Gender": "Female"})
        self.assertFalse(writer("PT1", "Male", {}, []))
        ws.update_cell.assert_not_called()


if __name__ == "__main__":
    unittest.main()
