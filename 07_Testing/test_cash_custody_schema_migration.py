import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "05_GoogleSheets" / "migrate_cash_custody_correctness.py"
spec = importlib.util.spec_from_file_location("custody_schema", PATH)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class Worksheet:
    def __init__(self, title, headers):
        self.title = title
        self.headers = list(headers)
        self.col_count = max(30, len(headers))
        self.writes = []

    def row_values(self, row):
        return list(self.headers) if row == 1 else []

    def add_cols(self, count):
        self.col_count += count

    def update(self, range_name, values, value_input_option=None):
        self.writes.append((range_name, values, value_input_option))
        self.headers.extend(values[0])


class Book:
    def __init__(self, sheets):
        self.sheets = {sheet.title: sheet for sheet in sheets}

    def worksheets(self):
        return list(self.sheets.values())

    def worksheet(self, title):
        return self.sheets[title]


def book_with(salary_headers):
    return Book([
        Worksheet("07_Expenses", ["Expense_ID", "Department"]),
        Worksheet(
            "21_Cash_Movement",
            ["Movement_ID", "Department", "Requested_Amount",
             "Received_Amount", "Difference"],
        ),
        Worksheet("13_Salary", salary_headers),
    ])


class CashCustodySchemaMigrationTests(unittest.TestCase):
    def test_dry_run_reports_only_missing_salary_headers(self):
        book = book_with(["Payment_ID", "Date", "Amount"])
        actions = migration.migrate(book, apply=False)
        self.assertEqual(actions, [{
            "sheet": "13_Salary",
            "add_headers": ["Department", "Paid_From", "Status", "Paid_At"],
        }])
        self.assertEqual(book.worksheet("13_Salary").writes, [])

    def test_apply_is_additive_and_repeatable(self):
        book = book_with(["Payment_ID", "Date", "Amount"])
        actions = migration.migrate(book, apply=True)
        self.assertEqual(len(actions), 1)
        headers = book.worksheet("13_Salary").headers
        self.assertEqual(
            headers[-4:], ["Department", "Paid_From", "Status", "Paid_At"]
        )
        self.assertEqual(migration.migrate(book, apply=True), [])

    def test_missing_money_tab_fails_loud(self):
        book = Book([Worksheet("13_Salary", ["Payment_ID"])])
        with self.assertRaisesRegex(RuntimeError, "Missing required sheet"):
            migration.plan_migration(book)


if __name__ == "__main__":
    unittest.main()
