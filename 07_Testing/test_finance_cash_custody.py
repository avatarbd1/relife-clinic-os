import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from gspread.utils import a1_to_rowcol


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("GOOGLE_SHEET_ID", "TEST_SHEET")
os.environ.setdefault("GOOGLE_CREDENTIALS_PATH", __file__)

import config  # noqa: E402
import sheets  # noqa: E402
import roles  # noqa: E402

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
    ] + cash_migration.EXPENSE_WORKFLOW_HEADERS

    def test_default_new_expense_is_clinic_expense(self):
        ws = WriteWorksheet(self.expense_headers)
        with patch.object(sheets, "_worksheet", return_value=ws):
            self.assertEqual(sheets.add_expense("ভাড়া", 100, "S1"), "EX0001")
        self.assertEqual(ws.appended[0][7], config.EXPENSE_TYPE_CLINIC)

    def test_new_expense_persists_explicit_department(self):
        headers = self.expense_headers + ["Department"]
        ws = WriteWorksheet(headers)
        with patch.object(sheets, "_worksheet", return_value=ws):
            sheets.add_expense("ভাড়া", 100, "S1", department="Dental")
        self.assertEqual(ws.appended[0][headers.index("Department")], "Dental")

    def test_invalid_finance_department_is_rejected(self):
        with self.assertRaises(ValueError):
            sheets.add_expense("ভাড়া", 100, "S1", department="All")

    def test_household_withdrawal_is_accepted(self):
        ws = WriteWorksheet(self.expense_headers)
        with patch.object(sheets, "_worksheet", return_value=ws):
            sheets.add_expense(
                "অন্যান্য", 50, "S1",
                expense_type=config.EXPENSE_TYPE_HOUSEHOLD,
                paid_from=config.CASH_CUSTODIAN_HOME_TREASURY,
            )
        self.assertEqual(ws.appended[0][7], config.EXPENSE_TYPE_HOUSEHOLD)
        self.assertEqual(
            ws.appended[0][self.expense_headers.index("Paid_From")],
            config.CASH_CUSTODIAN_HOME_TREASURY,
        )
        self.assertEqual(
            ws.appended[0][self.expense_headers.index("Status")], "Paid"
        )

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
        self.assertEqual(ws.appended[0][headers.index("Status")], "Pending")

    def test_cash_movement_persists_department_and_requested_amount(self):
        headers = cash_migration.CASH_MOVEMENT_HEADERS + [
            "Department", "From_Custodian_ID", "To_Custodian_ID",
            "Requested_Amount",
        ]
        ws = WriteWorksheet(headers)
        ws.title = config.SHEET_CASH_MOVEMENT
        with patch.object(sheets, "_worksheet", return_value=ws):
            sheets.add_cash_movement(
                "Reception", "Home Treasury", 500, "S1",
                department="Physio",
            )
        row = ws.appended[0]
        self.assertEqual(row[headers.index("Department")], "Physio")
        self.assertEqual(
            row[headers.index("From_Custodian_ID")], "Physio Reception Cash"
        )
        self.assertEqual(row[headers.index("Requested_Amount")], 500)

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


class ExpenseFinalizeWorksheet(WriteWorksheet):
    def __init__(self, status="Pending Approval"):
        headers = FinanceLedgerTests.expense_headers
        super().__init__(headers)
        row = [""] * len(headers)
        row[headers.index("Expense_ID")] = "EX0001"
        row[headers.index("Status")] = status
        self.rows = [row]
        self.batch_calls = []

    def get_all_values(self):
        return [list(self.headers)] + [list(row) for row in self.rows]

    def batch_update(self, data, value_input_option=None):
        self.batch_calls.append((data, value_input_option))
        for item in data:
            row, column = a1_to_rowcol(item["range"])
            self.rows[row - 2][column - 1] = item["values"][0][0]


class ExpenseApprovalWorkflowTests(unittest.TestCase):
    def test_reception_request_is_pending_and_unpaid(self):
        ws = WriteWorksheet(FinanceLedgerTests.expense_headers)
        with patch.object(sheets, "_worksheet", return_value=ws):
            expense_id = sheets.create_expense_request(
                "অন্যান্য", 300, "Reception One", "courier"
            )
        row = ws.appended[0]
        self.assertEqual(expense_id, "EX0001")
        self.assertEqual(
            row[ws.headers.index("Type")], config.EXPENSE_TYPE_CLINIC
        )
        self.assertEqual(
            row[ws.headers.index("Paid_From")],
            config.CASH_CUSTODIAN_RECEPTION,
        )
        self.assertEqual(row[ws.headers.index("Status")], "Pending Approval")
        self.assertEqual(row[ws.headers.index("Paid_At")], "")

    def test_owner_approval_then_reception_payment_is_exactly_once(self):
        ws = ExpenseFinalizeWorksheet()
        with patch.object(sheets, "_worksheet", return_value=ws):
            approved = sheets.finalize_expense_request(
                "EX0001", "Owner One", "Approved"
            )
            duplicate_approval = sheets.finalize_expense_request(
                "EX0001", "Owner Two", "Approved"
            )
            paid = sheets.mark_expense_paid("EX0001", "Reception One")
            duplicate_payment = sheets.mark_expense_paid(
                "EX0001", "Reception Two"
            )
        self.assertTrue(approved["ok"])
        self.assertFalse(duplicate_approval["ok"])
        self.assertEqual(duplicate_approval["status"], "Approved")
        self.assertTrue(paid["ok"])
        self.assertFalse(duplicate_payment["ok"])
        self.assertEqual(duplicate_payment["status"], "Paid")
        self.assertEqual(
            ws.rows[0][ws.headers.index("Approved_By")], "Owner One"
        )
        self.assertEqual(
            ws.rows[0][ws.headers.index("Paid_By")], "Reception One"
        )
        self.assertEqual(len(ws.batch_calls), 2)

    def test_rejected_request_cannot_be_paid(self):
        ws = ExpenseFinalizeWorksheet()
        with patch.object(sheets, "_worksheet", return_value=ws):
            rejected = sheets.finalize_expense_request(
                "EX0001", "Owner One", "Rejected"
            )
            paid = sheets.mark_expense_paid("EX0001", "Reception One")
        self.assertTrue(rejected["ok"])
        self.assertFalse(paid["ok"])
        self.assertEqual(paid["status"], "Rejected")

    def test_monthly_total_excludes_pending_and_household(self):
        records = [
            {"Date": "2026-08-01", "Amount": 100, "Type": "Clinic Expense", "Status": "Paid"},
            {"Date": "2026-08-02", "Amount": 200, "Type": "Clinic Expense", "Status": "Pending Approval"},
            {"Date": "2026-08-03", "Amount": 300, "Type": "Household Withdrawal", "Status": "Paid"},
        ]
        with patch.object(sheets, "_worksheet", return_value=object()), patch.object(
            sheets, "safe_get_all_records", return_value=records
        ):
            total = sheets.get_expense_total_for_month("2026-08")
        self.assertEqual(total, 100)

    def test_daily_custody_reconciliation(self):
        payment_ws, expense_ws, movement_ws = object(), object(), object()
        records = {
            payment_ws: [
                {"Date": "2026-08-11", "Amount": 10000, "Payment_Method": "Cash"},
                {"Date": "2026-08-11", "Amount": 500, "Payment_Method": "bKash"},
            ],
            expense_ws: [
                {"Date": "2026-08-11", "Amount": 500, "Type": "Clinic Expense", "Status": "Paid", "Paid_From": "Reception"},
                {"Date": "2026-08-11", "Amount": 1000, "Type": "Clinic Expense", "Status": "Paid", "Paid_From": "Home Treasury"},
                {"Date": "2026-08-11", "Amount": 2000, "Type": "Household Withdrawal", "Status": "Paid", "Paid_From": "Home Treasury"},
            ],
            movement_ws: [
                {"Date": "2026-08-11", "Amount": 7000, "From_Custodian": "Reception", "To_Custodian": "Home Treasury", "Status": "Accepted"},
                {"Date": "2026-08-11", "Amount": 900, "From_Custodian": "Reception", "To_Custodian": "Home Treasury", "Status": "Pending"},
            ],
        }
        with patch.object(
            sheets,
            "_worksheet",
            side_effect=[payment_ws, expense_ws, movement_ws],
        ), patch.object(
            sheets,
            "safe_get_all_records",
            side_effect=lambda ws: records[ws],
        ):
            summary = sheets.get_cash_custody_summary("2026-08-11")
        self.assertEqual(summary["Reception_Balance"], 2500)
        self.assertEqual(summary["Home_Balance"], 4000)


class FinalizeWorksheet(WriteWorksheet):
    def __init__(self, movement_id="CM0001", status="Pending"):
        super().__init__(cash_migration.CASH_MOVEMENT_HEADERS)
        self.title = config.SHEET_CASH_MOVEMENT
        row = [""] * len(self.headers)
        row[self.headers.index("Movement_ID")] = movement_id
        row[self.headers.index("Status")] = status
        self.rows = [row]
        self.batch_calls = []

    def get_all_values(self):
        return [list(self.headers)] + [list(row) for row in self.rows]

    def batch_update(self, data, value_input_option=None):
        self.batch_calls.append((data, value_input_option))
        for item in data:
            row, column = a1_to_rowcol(item["range"])
            self.rows[row - 2][column - 1] = item["values"][0][0]


class CashHandoverConfirmationTests(unittest.TestCase):
    def test_pending_movements_are_sorted(self):
        records = [
            {"Movement_ID": "CM1", "Status": "Pending", "Timestamp": "09:00"},
            {"Movement_ID": "CM2", "Status": "Accepted", "Timestamp": "11:00"},
            {"Movement_ID": "CM3", "Status": "Pending", "Timestamp": "10:00"},
        ]
        with patch.object(sheets, "_worksheet", return_value=object()), patch.object(
            sheets, "safe_get_all_records", return_value=records
        ):
            result = sheets.get_pending_cash_movements()
        self.assertEqual([row["Movement_ID"] for row in result], ["CM3", "CM1"])

    def test_pending_handover_is_accepted_exactly_once(self):
        ws = FinalizeWorksheet()
        with patch.object(sheets, "_worksheet", return_value=ws):
            first = sheets.finalize_cash_movement("CM0001", "Owner One")
            second = sheets.finalize_cash_movement("CM0001", "Owner Two")
        self.assertTrue(first["ok"])
        self.assertEqual(first["status"], "Accepted")
        self.assertFalse(second["ok"])
        self.assertEqual(second["reason"], "already_finalized")
        self.assertEqual(second["status"], "Accepted")
        self.assertEqual(len(ws.batch_calls), 1)
        self.assertEqual(
            ws.rows[0][ws.headers.index("Confirmed_By")],
            "Owner One",
        )

    def test_rejection_and_invalid_decision(self):
        ws = FinalizeWorksheet()
        with patch.object(sheets, "_worksheet", return_value=ws):
            result = sheets.finalize_cash_movement(
                "CM0001", "Manager One", "Rejected"
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "Rejected")
        with self.assertRaises(ValueError):
            sheets.finalize_cash_movement(
                "CM0002", "Manager One", "Cancelled"
            )

    def test_missing_confirmation_columns_fail_closed(self):
        ws = WriteWorksheet(cash_migration.CASH_MOVEMENT_HEADERS[:-3])
        ws.title = config.SHEET_CASH_MOVEMENT
        with patch.object(sheets, "_worksheet", return_value=ws):
            with self.assertRaises(RuntimeError):
                sheets.add_cash_movement(
                    "Reception", "Home Treasury", 500, "S1"
                )


class CashHandoverRoleTests(unittest.TestCase):
    def test_reception_can_handover_but_cannot_receive(self):
        self.assertTrue(
            roles.can_access("Receptionist", roles.MENU_CASH_HANDOVER)
        )
        self.assertTrue(
            roles.can_access("Receptionist", roles.MENU_CASH_MOVEMENTS)
        )
        self.assertFalse(
            roles.can_access("Receptionist", roles.MENU_CASH_RECEIVE)
        )

    def test_owner_and_manager_can_finalize_but_therapist_cannot(self):
        for role in ("Owner", "Manager"):
            with self.subTest(role=role):
                self.assertTrue(
                    roles.can_access(role, roles.MENU_CASH_RECEIVE)
                )
        self.assertFalse(
            roles.can_access("Therapist", roles.MENU_CASH_RECEIVE)
        )
        self.assertFalse(
            roles.can_access("Therapist", roles.MENU_CASH_HANDOVER)
        )

    def test_expense_permissions_match_custody_roles(self):
        self.assertTrue(roles.can_access(
            "Receptionist", roles.MENU_SMALL_EXPENSE_REQUEST
        ))
        self.assertTrue(roles.can_access(
            "Receptionist", roles.MENU_APPROVED_EXPENSES
        ))
        self.assertFalse(roles.can_access(
            "Receptionist", roles.MENU_EXPENSE_APPROVAL
        ))
        self.assertTrue(roles.can_access(
            "Owner", roles.MENU_EXPENSE_APPROVAL
        ))
        self.assertTrue(roles.can_access(
            "Owner", roles.MENU_HOUSEHOLD_WITHDRAWAL
        ))
        self.assertFalse(roles.can_access(
            "Manager", roles.MENU_EXPENSE_APPROVAL
        ))

    def test_bot_wires_cash_handover_handlers(self):
        source = (BOT_DIR / "bot.py").read_text(encoding="utf-8")
        for handler in (
            "cash_handover_start",
            "cash_receive_start",
            "cash_finalize_callback",
            "cash_movements_start",
            "small_expense_start",
            "expense_approval_start",
            "expense_approval_callback",
            "approved_expenses_start",
            "expense_paid_callback",
            "household_withdrawal_start",
            "custody_balance_start",
            "physio_finance_dashboard_start",
            "dental_finance_dashboard_start",
            "combined_business_summary_start",
            "cash_department_callback",
            "cost_department_callback",
        ):
            with self.subTest(handler=handler):
                self.assertIn(handler, source)

    def test_owner_alone_receives_three_financial_dashboard_views(self):
        owner_items = roles.ROLE_FINANCE_ITEMS[roles.Role.OWNER]
        for item in (
            roles.MENU_PHYSIO_FINANCE_DASHBOARD,
            roles.MENU_DENTAL_FINANCE_DASHBOARD,
            roles.MENU_COMBINED_BUSINESS_SUMMARY,
        ):
            self.assertIn(item, owner_items)
            self.assertTrue(roles.can_access("Owner", item))
            self.assertNotIn(item, roles.ROLE_FINANCE_ITEMS[roles.Role.RECEPTIONIST])
            self.assertNotIn(item, roles.ROLE_FINANCE_ITEMS[roles.Role.MANAGER])
            self.assertFalse(roles.can_access("Receptionist", item))
            self.assertFalse(roles.can_access("Manager", item))


class OwnerFinancialDashboardTests(unittest.TestCase):
    def test_department_views_preserve_scope_and_opening_balances(self):
        payment_ws, expense_ws, movement_ws = object(), object(), object()
        records = {
            payment_ws: [
                {"Date": "2026-08-10", "Department": "Physio", "Amount": 1000, "Payment_Method": "Cash"},
                {"Date": "2026-08-11", "Department": "Physio", "Amount": 500, "Payment_Method": "Cash"},
                {"Date": "2026-08-11", "Department": "Dental", "Amount": 800, "Payment_Method": "bKash"},
                {"Date": "2026-08-11", "Department": "", "Amount": 9999, "Payment_Method": "Cash"},
            ],
            expense_ws: [
                {"Date": "2026-08-11", "Department": "Physio", "Amount": 100, "Type": "Clinic Expense", "Status": "Paid", "Paid_From": "Reception"},
                {"Date": "2026-08-11", "Department": "Dental", "Amount": 50, "Type": "Household Withdrawal", "Status": "Paid", "Paid_From": "Home Treasury"},
            ],
            movement_ws: [
                {"Date": "2026-08-10", "Department": "Physio", "Received_Amount": 400, "Status": "Accepted", "From_Custodian_ID": "Physio Reception Cash", "To_Custodian_ID": "Home Treasury"},
                {"Date": "2026-08-11", "Department": "Physio", "Requested_Amount": 300, "Received_Amount": 250, "Status": "Accepted", "From_Custodian_ID": "Physio Reception Cash", "To_Custodian_ID": "Home Treasury"},
            ],
        }
        with patch.object(sheets, "_worksheet", side_effect=[payment_ws, expense_ws, movement_ws]), patch.object(
            sheets, "safe_get_all_records", side_effect=lambda ws: records[ws]
        ):
            data = sheets.get_owner_financial_dashboard("2026-08-11")

        physio = data["Physio"]
        dental = data["Dental"]
        combined = data["Combined"]
        self.assertEqual(physio["Today_Collection"], 500)
        self.assertEqual(dental["Today_Collection"], 800)
        self.assertEqual(physio["Opening"]["Reception"], 600)
        self.assertEqual(physio["Opening"]["Home Treasury"], 400)
        self.assertEqual(physio["Closing"]["Reception"], 750)
        self.assertEqual(physio["Closing"]["Home Treasury"], 650)
        self.assertEqual(dental["Closing"]["Digital/Bank"], 800)
        self.assertEqual(combined["Today_Collection"], 1300)
        self.assertEqual(combined["Unclassified_Rows"]["Payments"], 1)

    def test_missing_department_never_enters_department_totals(self):
        tabs = [object(), object(), object()]
        with patch.object(sheets, "_worksheet", side_effect=tabs), patch.object(
            sheets,
            "safe_get_all_records",
            side_effect=[[{"Date": "2026-08-11", "Amount": 100}], [], []],
        ):
            data = sheets.get_owner_financial_dashboard("2026-08-11")
        self.assertEqual(data["Combined"]["Today_Collection"], 0)
        self.assertEqual(data["Combined"]["Unclassified_Rows"]["Payments"], 1)


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
            [
                "add_expense_type",
                "add_expense_workflow_columns",
                "create_cash_movement",
            ],
        )
        cash_migration.migrate(book, apply=True)
        self.assertEqual(book.worksheet("07_Expenses").rows, legacy_rows)
        self.assertIn("Type", book.worksheet("07_Expenses").headers)
        self.assertEqual(
            book.worksheet("07_Expenses").headers[-7:],
            cash_migration.EXPENSE_WORKFLOW_HEADERS,
        )
        self.assertEqual(cash_migration.migrate(book, apply=True), [])

    def test_existing_cash_ledger_gets_confirmation_columns_only(self):
        book = FakeBook()
        cash_headers = cash_migration.CASH_MOVEMENT_HEADERS[:-3]
        cash_rows = [["CM0001", "2026-08-11", "Reception", "Home Treasury", 500]]
        book.tabs["21_Cash_Movement"] = FakeMigrationWorksheet(
            "21_Cash_Movement", cash_headers, rows=cash_rows
        )
        book.tabs["07_Expenses"].headers.extend(
            ["Type"] + cash_migration.EXPENSE_WORKFLOW_HEADERS
        )
        self.assertEqual(
            cash_migration.migrate(book, apply=False),
            ["add_cash_handover_columns"],
        )
        cash_migration.migrate(book, apply=True)
        self.assertEqual(
            book.tabs["21_Cash_Movement"].headers,
            cash_migration.CASH_MOVEMENT_HEADERS,
        )
        self.assertEqual(book.tabs["21_Cash_Movement"].rows, cash_rows)
        self.assertEqual(cash_migration.migrate(book, apply=True), [])


if __name__ == "__main__":
    unittest.main()
