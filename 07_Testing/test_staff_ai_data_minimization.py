import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "03_Bot" / "staff_ai_query.py"
TREE = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))


def load_filter_policy():
    selected = []
    for node in TREE.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "AI_SAFE_FIELDS"
            for target in node.targets
        ):
            selected.append(node)
        if isinstance(node, ast.FunctionDef) and node.name == "_filter_ai_safe_records":
            selected.append(node)
    namespace = {}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(MODULE_PATH), "exec"), namespace)
    return namespace["AI_SAFE_FIELDS"], namespace["_filter_ai_safe_records"]


class StaffAiDataMinimizationTests(unittest.TestCase):
    def test_direct_identifiers_are_not_allowed_for_any_sheet(self):
        policy, _ = load_filter_policy()
        forbidden = {
            "Patient_ID", "Patient_Name", "Full_Name", "Phone", "Alternate_Phone",
            "Address", "DOB", "Staff_ID", "Staff_Name", "Receipt_No",
            "Payment_Received_By",
        }
        for sheet_name, allowed_fields in policy.items():
            with self.subTest(sheet=sheet_name):
                self.assertTrue(forbidden.isdisjoint(allowed_fields))

    def test_patient_record_is_reduced_to_whitelisted_fields(self):
        _, filter_records = load_filter_policy()
        records = [{
            "Patient_ID": "PT0001",
            "Full_Name": "Private Patient",
            "Phone": "01700000000",
            "Address": "Private address",
            "Diagnosis": "Private diagnosis",
            "Registration_Date": "2026-08-10",
            "Total_Bill": 1000,
            "Paid": 700,
            "Due": 300,
            "Status": "Active",
        }]

        self.assertEqual(filter_records("02_Patients", records), [{
            "Registration_Date": "2026-08-10",
            "Total_Bill": 1000,
            "Paid": 700,
            "Due": 300,
            "Status": "Active",
        }])

    def test_summarizer_filters_before_serializing(self):
        summarizer = next(
            node for node in TREE.body
            if isinstance(node, ast.FunctionDef) and node.name == "_summarize_answer"
        )
        called_helpers = {
            node.func.id for node in ast.walk(summarizer)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("_filter_ai_safe_records", called_helpers)


if __name__ == "__main__":
    unittest.main()
