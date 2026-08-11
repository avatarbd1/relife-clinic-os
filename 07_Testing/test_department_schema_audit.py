import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "05_GoogleSheets" / "audit_department_schema.py"
SPEC = importlib.util.spec_from_file_location("department_schema_audit", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Worksheet:
    def __init__(self, title, headers, records=None):
        self.title = title
        self.headers = list(headers)
        self.records = list(records or [])
        self.row_count = len(self.records) + 1

    def row_values(self, row):
        return self.headers if row == 1 else []

    def get_all_records(self):
        return list(self.records)


class Book:
    def __init__(self, sheets):
        self.sheets = {sheet.title: sheet for sheet in sheets}

    def worksheets(self):
        return list(self.sheets.values())

    def worksheet(self, title):
        return self.sheets[title]


def complete_book():
    sheets = [
        Worksheet(
            MODULE.STAFF_SHEET,
            ["Staff_ID", *sorted(MODULE.STAFF_REQUIRED_HEADERS)],
        ),
        Worksheet(MODULE.MAPPING_SHEET, ["Staff_ID", "Department", "Status"]),
    ]
    sheets.extend(
        Worksheet(title, ["Record_ID", "Department"], [{"Department": "Physio"}])
        for title in MODULE.REQUIRED_RECORD_SHEETS
    )
    return Book(sheets)


class DepartmentSchemaAuditTests(unittest.TestCase):
    def test_complete_classified_schema_is_enforcement_ready(self):
        report = MODULE.audit_department_schema(complete_book())
        self.assertTrue(report["enforcement_ready"])
        self.assertEqual(report["unclassified_count"], 0)

    def test_missing_and_invalid_departments_enter_review_queue(self):
        book = complete_book()
        book.sheets["02_Patients"] = Worksheet(
            "02_Patients",
            ["Patient_ID", "Department"],
            [
                {"Department": ""},
                {"Department": "physio"},
                {"Department": "Dental"},
            ],
        )
        report = MODULE.audit_department_schema(book)
        patient = next(item for item in report["sheets"] if item["sheet"] == "02_Patients")
        self.assertFalse(report["enforcement_ready"])
        self.assertEqual(patient["missing_department_rows"], [2])
        self.assertEqual(patient["invalid_department_rows"], [3])
        self.assertEqual(patient["valid_rows"], 1)

    def test_missing_tabs_and_headers_fail_closed_without_mutation(self):
        staff = Worksheet(MODULE.STAFF_SHEET, ["Staff_ID"])
        patients = Worksheet("02_Patients", ["Patient_ID"], [{"Patient_ID": "P1"}])
        book = Book([staff, patients])
        before = patients.row_values(1)[:]
        report = MODULE.audit_department_schema(book)
        self.assertFalse(report["enforcement_ready"])
        self.assertIn(MODULE.MAPPING_SHEET, [MODULE.MAPPING_SHEET] if not report["mapping_sheet_present"] else [])
        self.assertIn("04_Appointments", report["missing_tabs"])
        self.assertIn("02_Patients", report["missing_department_headers"])
        self.assertEqual(patients.row_values(1), before)


if __name__ == "__main__":
    unittest.main()
