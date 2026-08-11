import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "05_GoogleSheets" / "migrate_department_schema.py"
SPEC = importlib.util.spec_from_file_location("department_schema_migration", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class Worksheet:
    def __init__(self, title, headers):
        self.title = title
        self.headers = list(headers)
        self.col_count = len(self.headers)
        self.appended = []

    def row_values(self, row):
        return list(self.headers) if row == 1 else []

    def add_cols(self, count):
        self.col_count += count

    def update_cell(self, row, column, value):
        assert row == 1
        while len(self.headers) < column:
            self.headers.append("")
        self.headers[column - 1] = value

    def append_row(self, row, value_input_option=None):
        self.headers = list(row)
        self.appended.append(list(row))


class Book:
    def __init__(self, sheets):
        self.sheets = {sheet.title: sheet for sheet in sheets}

    def worksheets(self):
        return list(self.sheets.values())

    def worksheet(self, title):
        return self.sheets[title]

    def add_worksheet(self, title, rows, cols):
        ws = Worksheet(title, [])
        ws.col_count = cols
        self.sheets[title] = ws
        return ws


def legacy_book():
    names = [
        MODULE.STAFF_SHEET,
        "02_Patients", "04_Appointments", "05_Treatments", "06_Payments",
        "07_Expenses", "09_Inventory", "10_Assessments", "11_Packages",
        "12_Treatment_Plans", "14_Reports", "16_Delete_Log",
        "17_Inventory_Log", "20_Data_Audit", "21_Cash_Movement",
    ]
    return Book([Worksheet(name, ["ID"]) for name in names])


class DepartmentSchemaMigrationTests(unittest.TestCase):
    def test_dry_run_is_non_mutating_and_complete(self):
        book = legacy_book()
        before = {name: ws.headers[:] for name, ws in book.sheets.items()}
        actions = MODULE.migrate(book)
        self.assertTrue(actions)
        self.assertEqual(before, {name: ws.headers[:] for name, ws in book.sheets.items()})
        self.assertTrue(any(a.sheet == MODULE.MAPPING_SHEET for a in actions))
        self.assertTrue(any(a.sheet == "Dental_Procedures" for a in actions))

    def test_apply_requires_backup_and_snapshot(self):
        book = legacy_book()
        with self.assertRaisesRegex(RuntimeError, "backup"):
            MODULE.migrate(book, apply=True)
        with self.assertRaisesRegex(RuntimeError, "snapshot"):
            MODULE.migrate(book, apply=True, backup_confirmed=True)

    def test_apply_is_additive_and_idempotent(self):
        book = legacy_book()
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
            handle.write("schema snapshot")
            snapshot = handle.name
        try:
            actions = MODULE.migrate(
                book,
                apply=True,
                backup_confirmed=True,
                schema_snapshot=snapshot,
            )
            self.assertTrue(actions)
            self.assertEqual(MODULE.plan_migration(book), [])
            self.assertEqual(
                MODULE.migrate(
                    book,
                    apply=True,
                    backup_confirmed=True,
                    schema_snapshot=snapshot,
                ),
                [],
            )
            self.assertIn("Department", book.worksheet("05_Treatments").headers)
            self.assertEqual(
                book.worksheet(MODULE.MAPPING_SHEET).headers,
                MODULE.MAPPING_HEADERS,
            )
        finally:
            Path(snapshot).unlink(missing_ok=True)

    def test_cash_movement_receives_department_custody_fields(self):
        book = legacy_book()
        actions = MODULE.plan_migration(book)
        cash = next(a for a in actions if a.sheet == "21_Cash_Movement" and a.kind == "add_headers")
        self.assertIn("Department", cash.headers)
        self.assertIn("Requested_Amount", cash.headers)
        self.assertIn("Received_Amount", cash.headers)
        self.assertIn("Difference", cash.headers)


if __name__ == "__main__":
    unittest.main()
