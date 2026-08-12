import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / "03_Bot" / "bot.py"


def function(name):
    tree = ast.parse(BOT.read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def source(name):
    return ast.unparse(function(name))


class ClinicalFinalWriteSafetyTests(unittest.TestCase):
    def test_dashboard_finalizer_reauthorizes_patient_clinical_write(self):
        body = source("pt_dashboard_done_callback")
        self.assertIn("_authorized_patient_action", body)
        self.assertIn("CLINICAL_WRITE", body)
        self.assertIn("MENU_TREATMENT_NOTE", body)

    def test_dashboard_appointment_completion_is_scoped(self):
        body = source("pt_dashboard_done_callback")
        self.assertIn("get_appointment_by_id_for_staff", body)
        self.assertIn("update_appointment_status_for_staff", body)
        self.assertNotIn("sheets.update_appointment_status,", body)

    def test_treatment_plan_finalizer_reauthorizes_live(self):
        body = source("tplan_confirm")
        self.assertIn("_authorized_patient_action", body)
        self.assertIn("CLINICAL_WRITE", body)
        self.assertIn("MENU_TREATMENT_PLAN", body)
        self.assertIn('cached["Department"]', body)

    def test_finalizers_do_not_expose_raw_exception_text(self):
        for name in ["pt_dashboard_done_callback", "tplan_confirm"]:
            with self.subTest(name=name):
                self.assertNotIn("Error:", source(name))


if __name__ == "__main__":
    unittest.main()
