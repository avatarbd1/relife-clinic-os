import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("GOOGLE_SHEET_ID", "TEST_SHEET")
os.environ.setdefault("GOOGLE_CREDENTIALS_PATH", __file__)

import config  # noqa: E402
import sheets  # noqa: E402

MIGRATION_PATH = ROOT / "05_GoogleSheets" / "migrate_cash_custody_foundation.py"
spec = importlib.util.spec_from_file_location("cash_migration", MIGRATION_PATH)
cash_migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cash_migration)


class WriteWorksheet:
    title = "07_Expenses"
    id = 7

    def __init__(self, headers, ids=None):
        self.spreadsheet_id = config.GOOGLE_SHEET_ID
        self.headers = list(headers)
        self.ids = ids or []
        self.appended = []

    def row_values(self, row):
        return list(self.headers) if row == 1 else []

    def col_values(self, _column):
        return [self.headers[0]] + list(self.ids)

    def append_row(self, row, value_input_option=None):
        self.appended.append(list(row))


class FinanceLedgerTests(unittest.TestCase):
    expense_headers = [
        "Expense_ID", "Date", "Category", "Amount", "Added_By",
        "Timestamp", "Note", "Type",
    ]

    def test_default_new_expense_is_clinic_expense(self):
        ws = WriteWorksheet(self.expense_headers)
        with patch.object(sheets, "_worksheet", return_value=ws):
            self.assertEqual(sheets.add_expense("ভাড়া", 100, "S1"), "EX0001")
        self.assertEqual(ws.appended[0][7], config.EXPENSE_TYPE_CLINIC)

    def test_household_withdrawal_is_accepted(self):
        ws = WriteWorksheet(self.expense_headers)
        with patch.object(sheets, "_worksheet", return_value=ws):
            sheets.add_expense(
                "অন্যান্য", 50, "S1",
                expense_type=config.EXPENSE_TYPE_HOUSEHOLD,
            )
        self.assertEqual(ws.appended[0][7], config.EXPENSE_TYPE_HOUSEHOLD)

    def test_invalid_expense_type_is_rejected_before_write(self):
        with self.assertRaises(ValueError):
            sheets.add_expense("ভাড়া", 100, "S1", expense_type="Transfer")

    def test_legacy_blank_is_unclassified_and_not_monthly_clinic_expense(self):
        records = [
            {"Date": "2026-08-01", "Amount": 100, "Type": ""},
            {"Date": "2026-08-02", "Amount": 40, "Type": "Clinic Expense"},
        ]
        ws = type("ReadWorksheet", (), {"title": "07_Expenses"})()
        with patch.object(sheets, "_worksheet", return_value=ws), patch.object(
            sheets, "safe_get_all_records", return_value=records
        ):
            rows = sheets.get_expenses_for_date("2026-08-01")
            total = sheets.get_expense_total_for_month("2026-08")
        self.assertEqual(rows[0]["Type"], config.EXPENSE_TYPE_UNCLASSIFIED)
        self.assertEqual(total, 40)

    def test_valid_cash_movement_is_accepted(self):
        headers = cash_migration.CASH_MOVEMENT_HEADERS
        ws = WriteWorksheet(headers)
        ws.title = config.SHEET_CASH_MOVEMENT
        ws.id = 21
        with patch.object(sheets, "_worksheet", return_value=ws):
            movement_id = sheets.add_cash_movement(
                "Reception", "Home Treasury", 500, "S1", "daily handover"
            )
        self.assertEqual(movement_id, "CM0001")
        self.assertEqual(ws.appended[0][2:5], ["Reception", "Home Treasury", 500.0])

    def test_invalid_custodian_is_rejected(self):
        with self.assertRaises(ValueError):
            sheets.add_cash_movement("Pocket", "Bank", 1, "S1")

    def test_zero_and_negative_amounts_are_rejected(self):
        for amount in (0, -1):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                sheets.add_cash_movement("Reception", "Bank", amount, "S1")

    def test_same_custodian_is_rejected(self):
        with self.assertRaises(ValueError):
            sheets.add_cash_movement("Bank", "Bank", 1, "S1")

    def test_cash_movement_date_filtering_and_sorting(self):
        records = [
            {"Date": "2026-08-11", "Timestamp": "09:00", "Movement_ID": "CM1"},
            {"Date": "2026-08-10", "Timestamp": "12:00", "Movement_ID": "CM2"},
            {"Date": "2026-08-11", "Timestamp": "10:00", "Movement_ID": "CM3"},
        ]
        with patch.object(sheets, "_worksheet", return_value=object()), patch.object(
            sheets, "safe_get_all_records", return_value=records
        ):
            result = sheets.get_cash_movements_for_date("2026-08-11")
        self.assertEqual([row["Movement_ID"] for row in result], ["CM3", "CM1"])


class FakeMigrationWorksheet:
    def __init__(self, title, headers, rows=None):
        self.title = title
        self.headers = list(headers)
        self.rows = list(rows or [])
        self.col_count = len(headers)

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
        if not self.headers:
            self.headers = list(row)


class FakeBook:
    def __init__(self):
        self.tabs = {
            "07_Expenses": FakeMigrationWorksheet(
                "07_Expenses",
                ["Expense_ID", "Date", "Category", "Amount", "Added_By", "Timestamp", "Note"],
                rows=[["EX0001", "2026-01-01", "ভাড়া", 100]],
            )
        }

    def worksheets(self):
        return list(self.tabs.values())

    def worksheet(self, title):
        return self.tabs[title]

    def add_worksheet(self, title, rows, cols):
        ws = FakeMigrationWorksheet(title, [])
        ws.col_count = cols
        self.tabs[title] = ws
        return ws


class MigrationTests(unittest.TestCase):
    def test_migration_is_idempotent_and_non_destructive(self):
        book = FakeBook()
        legacy_rows = list(book.worksheet("07_Expenses").rows)
        self.assertEqual(
            cash_migration.migrate(book, apply=False),
            ["add_expense_type", "create_cash_movement"],
        )
        cash_migration.migrate(book, apply=True)
        self.assertEqual(book.worksheet("07_Expenses").rows, legacy_rows)
        self.assertEqual(book.worksheet("07_Expenses").headers[-1], "Type")
        self.assertEqual(cash_migration.migrate(book, apply=True), [])


if __name__ == "__main__":
    unittest.main()
