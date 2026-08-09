import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "05_GoogleSheets" / "audit_live_schema.py"
SPEC = importlib.util.spec_from_file_location("audit_live_schema", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


class LiveSchemaAuditTests(unittest.TestCase):
    def test_clean_structure_passes_without_exposing_values(self):
        headers = ["Patient_ID", *audit.UNIFIED_HEADERS]
        result = audit.audit_values("02_Patients", [headers, ["PT-1"]])
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["rows"], 1)
        self.assertNotIn("PT-1", str(result))

    def test_duplicate_id_header_and_formula_defects_are_counted(self):
        values = [
            ["Patient_ID", "Patient_ID", "", *audit.UNIFIED_HEADERS],
            ["PT-1", "", "", *([""] * len(audit.UNIFIED_HEADERS))],
            ["PT-1", "", "", "#REF!"],
        ]
        result = audit.audit_values("02_Patients", values)
        self.assertEqual(result["status"], "REVIEW")
        self.assertEqual(result["duplicate_headers"], ["Patient_ID"])
        self.assertEqual(result["blank_headers"], 1)
        self.assertEqual(result["duplicate_primary_ids"], 1)
        self.assertEqual(result["formula_errors"], 1)

    def test_empty_sheet_is_reported_safely(self):
        result = audit.audit_values("02_Patients", [])
        self.assertEqual(result["status"], "EMPTY")
        self.assertEqual(result["rows"], 0)


if __name__ == "__main__":
    unittest.main()
