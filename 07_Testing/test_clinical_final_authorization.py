import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))


def function(name):
    tree = ast.parse((BOT_DIR / "bot.py").read_text(encoding="utf-8"))
    return next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    )


def call_names(node):
    names = set()
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        parts, current = [], item.func
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        names.add(".".join(reversed(parts)))
    return names


class ClinicalFinalAuthorizationTests(unittest.TestCase):
    def test_report_receive_reauthorizes_clinical_write(self):
        node = function("report_receive")
        self.assertIn("_authorized_patient_action", call_names(node))
        source = ast.unparse(node)
        self.assertIn("AccessAction.CLINICAL_WRITE", source)
        self.assertLess(
            source.index("_authorized_patient_action"),
            source.index("sheets.add_report"),
        )

    def test_treatment_final_save_reauthorizes_before_sheet_write(self):
        node = function("_treat_do_save")
        self.assertIn("_authorized_patient_action", call_names(node))
        source = ast.unparse(node)
        self.assertIn("AccessAction.CLINICAL_WRITE", source)
        self.assertLess(
            source.index("_authorized_patient_action"),
            source.index("sheets.add_treatment_note"),
        )

    def test_stale_history_callbacks_reauthorize_patient(self):
        for name in [
            "thist_progress_callback",
            "thist_date_callback",
            "thist_nav_callback",
            "thist_back_to_dates_callback",
        ]:
            with self.subTest(name=name):
                self.assertIn(
                    "_authorized_treatment_history_patient",
                    call_names(function(name)),
                )

    def test_history_guard_is_live_clinical_read(self):
        node = function("_authorized_treatment_history_patient")
        self.assertIn("_authorized_patient_action", call_names(node))
        self.assertIn("AccessAction.CLINICAL_READ", ast.unparse(node))


if __name__ == "__main__":
    unittest.main()
