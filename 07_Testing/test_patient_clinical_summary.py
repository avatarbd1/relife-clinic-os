import os
import sys
import unittest
from unittest.mock import patch


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOT_DIR = os.path.join(ROOT, "03_Bot")
if BOT_DIR not in sys.path:
    sys.path.insert(0, BOT_DIR)
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("GOOGLE_SHEET_ID", "TEST_SHEET")
os.environ.setdefault("GOOGLE_CREDENTIALS_PATH", __file__)

import bot  # noqa: E402


class PhysioClinicalSummaryTests(unittest.TestCase):
    @patch.object(bot.sheets, "get_assessments_for_patient")
    @patch.object(bot.sheets, "get_active_plan_for_patient")
    def test_active_plan_and_latest_assessment_are_visible(self, active_plan, assessments):
        active_plan.return_value = {
            "Plan_ID": "PL0011",
            "Diagnosis": "Shoulder instability",
            "Sessions_Done": 2,
            "Total_Sessions": 14,
            "Exercise_Plan": "Shoulder elevation",
            "Electrotherapy_Plan": "EMS",
            "Manual_Therapy_Plan": "Deltoid and teres minor release",
        }
        assessments.return_value = [{
            "Assessment_ID": "AS0012",
            "Created_At": "2026-08-14 12:47 PM",
            "Test_Data": {"Mode": "Quick", "Findings": "Pain 1"},
        }]

        text = "\n".join(bot._physio_clinical_summary_lines("PT0101", {}))

        self.assertIn("রোগ/প্রধান সমস্যা: Shoulder instability", text)
        self.assertIn("AS0012", text)
        self.assertIn("Pain 1", text)
        self.assertIn("Session progress: 2/14", text)
        self.assertIn("Exercise: Shoulder elevation", text)
        self.assertIn("Electro: EMS", text)
        self.assertIn("Manual: Deltoid and teres minor release", text)

    @patch.object(bot.sheets, "get_assessments_for_patient", return_value=[])
    @patch.object(bot.sheets, "get_active_plan_for_patient", return_value=None)
    def test_missing_clinical_data_is_explicit(self, _active_plan, _assessments):
        text = "\n".join(bot._physio_clinical_summary_lines("PT0101", {}))
        self.assertIn("রোগ/প্রধান সমস্যা: এখনও যোগ হয়নি", text)
        self.assertIn("সর্বশেষ Assessment: এখনও যোগ হয়নি", text)
        self.assertIn("চলমান Plan: নেই", text)

    @patch.object(bot.sheets, "get_assessments_for_patient", return_value=[])
    @patch.object(bot.sheets, "get_active_plan_for_patient", return_value=None)
    def test_registered_diagnosis_has_priority(self, _active_plan, _assessments):
        lines = bot._physio_clinical_summary_lines(
            "PT0101", {"Diagnosis": "Frozen shoulder"}
        )
        self.assertIn("  রোগ/প্রধান সমস্যা: Frozen shoulder", lines)


if __name__ == "__main__":
    unittest.main()
