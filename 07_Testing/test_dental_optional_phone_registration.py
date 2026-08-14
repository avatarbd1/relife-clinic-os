import ast
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_SOURCE = (ROOT / "03_Bot" / "bot.py").read_text(encoding="utf-8")


def _load_missing_fields_helper():
    tree = ast.parse(BOT_SOURCE)
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "_REG_REQUIRED_ORDER"
            for target in node.targets
        ):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == "_reg_missing_fields":
            selected.append(node)
    namespace = {
        "config": types.SimpleNamespace(DEPARTMENT_DENTAL="Dental"),
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), "bot.py", "exec"), namespace)
    return namespace["_reg_missing_fields"]


class DentalOptionalPhoneRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.missing_fields = _load_missing_fields_helper()

    def test_dental_registration_does_not_require_phone(self):
        patient = {
            "Department": "Dental",
            "Full_Name": "Unknown Dental Patient",
            "Address": "Unknown",
            "Age": "30",
            "Phone": "",
        }
        self.assertEqual(self.missing_fields(patient), [])

    def test_physio_registration_still_requires_phone(self):
        patient = {
            "Department": "Physio",
            "Full_Name": "Physio Patient",
            "Address": "Dhaka",
            "Age": "30",
            "Phone": "",
        }
        self.assertEqual(self.missing_fields(patient), ["Phone"])

    def test_dental_still_requires_other_core_fields(self):
        self.assertEqual(
            self.missing_fields({"Department": "Dental"}),
            ["Full_Name", "Address", "Age"],
        )

    def test_confirmation_handles_blank_phone(self):
        self.assertIn("p.get('Phone') or 'দেওয়া হয়নি'", BOT_SOURCE)


if __name__ == "__main__":
    unittest.main()
