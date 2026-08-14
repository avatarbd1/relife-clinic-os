import importlib.util
import os
import sys
import unittest
from datetime import date
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
import bot  # noqa: E402

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

    def test_owner_and_reception_expense_categories_are_role_specific(self):
        self.assertIn("চেম্বার ভাড়া", sheets.OWNER_EXPENSE_CATEGORIES)
        self.assertNotIn("চেম্বার ভাড়া", sheets.RECEPTION_EXPENSE_CATEGORIES)
        self.assertIn("PT ব্যবহার্য পণ্য", sheets.RECEPTION_EXPENSE_CATEGORIES)
        self.assertIn("Dental Lab Bill", sheets.RECEPTION_EXPENSE_CATEGORIES)

    def test_expense_items_are_grouped_under_clear_categories(self):
        self.assertIn(
            "Ultrasound Gel", sheets.EXPENSE_ITEM_OPTIONS["PT ব্যবহার্য পণ্য"]
        )
        self.assertIn(
            "Composite", sheets.EXPENSE_ITEM_OPTIONS["Dental ব্যবহার্য পণ্য"]
        )
        self.assertIn(
            "Dental Handpiece", sheets.EXPENSE_ITEM_OPTIONS["যন্ত্রপাতি মেরামত"]
        )
        self.assertIn(
            "Receipt Book", sheets.EXPENSE_ITEM_OPTIONS["Printing ও Stationery"]
        )

    def test_expense_report_displays_saved_item_next_to_category(self):
        text = bot._expense_report_text(
            [{
                "Expense_ID": "EX0001",
                "Category": "PT ব্যবহার্য পণ্য",
                "Amount": 450,
                "Status": "Paid",
                "Paid_From": config.CASH_CUSTODIAN_RECEPTION,
                "Type": config.EXPENSE_TYPE_CLINIC,
                "Note": "Item: Ultrasound Gel | 2 bottles",
            }],
            "2026-08-14",
            "2026-08-14",
            roles.Role.OWNER.value,
        )
        self.assertIn("PT ব্যবহার্য পণ্য | Ultrasound Gel | ৳450", text)

    def test_generator_petrol_splits_40_60_without_double_counting(self):
        calls = []

        def capture(target_department, function, *args, **kwargs):
            calls.append((target_department, args[1], kwargs))
            return f"EX-{target_department}"

        with patch.object(sheets, "_expense_action_for_department", side_effect=capture):
            result = sheets.add_shared_expense(
                "Generator Petrol", 700, "Owner", note="5 litre"
            )

        self.assertEqual(result["Allocations"], {"Physio": 280, "Dental": 420})
        self.assertEqual(sum(item[1] for item in calls), 700)
        self.assertEqual([item[0] for item in calls], ["Physio", "Dental"])
        self.assertTrue(all(item[2]["status"] == "Paid" for item in calls))

    def test_wifi_splits_50_50_without_double_counting(self):
        calls = []

        def capture(target_department, function, *args, **kwargs):
            calls.append((target_department, args[1]))
            return f"EX-{target_department}"

        with patch.object(sheets, "_expense_action_for_department", side_effect=capture):
            result = sheets.add_shared_expense("Wi-Fi", 800, "Owner")

        self.assertEqual(result["Allocations"], {"Physio": 400, "Dental": 400})
        self.assertEqual(sum(item[1] for item in calls), 800)

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

    def test_cash_custody_range_aggregates_all_inclusive_days(self):
        payment_ws, expense_ws, movement_ws = object(), object(), object()
        records = {
            payment_ws: [
                {"Date": "2026-08-10", "Amount": 1000, "Payment_Method": "Cash"},
                {"Date": "2026-08-11", "Amount": 2000, "Payment_Method": "Cash"},
                {"Date": "2026-08-12", "Amount": 9000, "Payment_Method": "Cash"},
            ],
            expense_ws: [
                {"Date": "2026-08-10", "Amount": 100, "Type": "Clinic Expense", "Status": "Paid", "Paid_From": "Reception"},
                {"Date": "2026-08-11", "Amount": 200, "Type": "Clinic Expense", "Status": "Paid", "Paid_From": "Reception"},
            ],
            movement_ws: [
                {"Date": "2026-08-10", "Amount": 400, "From_Custodian": "Reception", "To_Custodian": "Home Treasury", "Status": "Accepted"},
                {"Date": "2026-08-11", "Amount": 600, "From_Custodian": "Reception", "To_Custodian": "Home Treasury", "Status": "Accepted"},
            ],
        }
        with patch.object(
            sheets, "_worksheet", side_effect=[payment_ws, expense_ws, movement_ws]
        ), patch.object(
            sheets, "safe_get_all_records", side_effect=lambda ws: records[ws]
        ):
            summary = sheets.get_cash_custody_summary(
                "2026-08-10", "2026-08-11"
            )
        self.assertEqual(summary["Cash_Collected"], 3000)
        self.assertEqual(summary["Reception_Expense"], 300)
        self.assertEqual(summary["Reception_Handover"], 1000)
        self.assertEqual(summary["Reception_Balance"], 1700)
        self.assertEqual(summary["Date"], "2026-08-10 — 2026-08-11")

    def test_previous_day_closing_carries_to_next_day_opening(self):
        payment_ws, expense_ws, movement_ws, salary_ws = (
            object(), object(), object(), object()
        )
        records = {
            payment_ws: [
                {"Date": "2026-07-31", "Amount": 200,
                 "Payment_Method": "Cash"},
                {"Date": "2026-08-13", "Amount": 1000,
                 "Payment_Method": "Cash"},
            ],
            expense_ws: [
                {"Date": "2026-07-31", "Amount": 400,
                 "Type": "Clinic Expense", "Status": "Paid",
                 "Paid_From": "Reception"},
                {"Date": "2026-08-13", "Amount": 800,
                 "Type": "Clinic Expense", "Status": "Paid",
                 "Paid_From": "Reception"},
            ],
            movement_ws: [],
            salary_ws: [],
        }
        with patch.object(
            sheets, "_worksheet",
            side_effect=[payment_ws, expense_ws, movement_ws, salary_ws],
        ), patch.object(
            sheets, "safe_get_all_records", side_effect=lambda ws: records[ws]
        ):
            summary = sheets.get_cash_custody_summary("2026-08-14")

        self.assertEqual(summary["Reception_Opening"], 200)
        self.assertEqual(summary["Reception_Balance"], 0)
        self.assertEqual(summary["Reception_Closing"], 200)

    def test_live_balance_uses_current_month_not_all_time_history(self):
        payment_ws, expense_ws, movement_ws, salary_ws = (
            object(), object(), object(), object()
        )
        records = {
            payment_ws: [
                {"Date": "2026-07-31", "Amount": 200,
                 "Payment_Method": "Cash"},
                {"Date": "2026-08-13", "Amount": 1000,
                 "Payment_Method": "Cash"},
            ],
            expense_ws: [
                {"Date": "2026-07-31", "Amount": 400,
                 "Type": "Clinic Expense", "Status": "Paid",
                 "Paid_From": "Reception"},
                {"Date": "2026-08-13", "Amount": 800,
                 "Type": "Clinic Expense", "Status": "Paid",
                 "Paid_From": "Reception"},
            ],
            movement_ws: [],
            salary_ws: [],
        }
        with patch.object(
            sheets, "_worksheet",
            side_effect=[payment_ws, expense_ws, movement_ws, salary_ws],
        ), patch.object(
            sheets, "safe_get_all_records", side_effect=lambda ws: records[ws]
        ):
            summary = sheets.get_cash_custody_summary(
                sheets._RECEPTION_BALANCE_EPOCH, "2026-08-14"
            )

        self.assertEqual(summary["Reception_Balance"], 200)
        self.assertEqual(summary["Reception_Opening"], 0)
        self.assertEqual(summary["Reception_Closing"], 200)

    def test_reconciliation_text_shows_opening_and_closing(self):
        summary = {
            "Date": "2026-08-14", "Start_Date": "2026-08-14",
            "End_Date": "2026-08-14", "Cash_Collected": 0,
            "Reception_Expense": 0, "Reception_Salary": 0,
            "Reception_Handover": 0, "Reception_In_Transit": 0,
            "Reception_Opening": 200, "Reception_Balance": 0,
            "Reception_Closing": 200,
        }
        text = bot._cash_custody_summary_text(summary, "Receptionist")
        self.assertIn("Opening cash: ৳200", text)
        self.assertIn("Net movement: ৳0", text)
        self.assertIn("Closing balance: ৳200", text)
        self.assertIn("পরের দিনের Opening cash", text)

    def test_expense_range_and_default_today_are_backward_compatible(self):
        records = [
            {"Date": "2026-08-10", "Amount": 100},
            {"Date": "2026-08-11", "Amount": 200},
            {"Date": "2026-08-12", "Amount": 300},
        ]
        with patch.object(sheets, "_worksheet", return_value=object()), patch.object(
            sheets, "safe_get_all_records", return_value=records
        ):
            ranged = sheets.get_expenses_for_date("2026-08-10", "2026-08-11")
            with patch.object(sheets, "bd_now") as now:
                now.return_value.strftime.return_value = "2026-08-12"
                defaulted = sheets.get_expenses_for_date()
        self.assertEqual(sum(row["Amount"] for row in ranged), 300)
        self.assertEqual([row["Amount"] for row in defaulted], [300])

    def test_financial_report_shortcut_boundaries_use_sunday_week_start(self):
        today = date(2026, 8, 12)
        self.assertEqual(
            bot._financial_report_date_range("today", today),
            ("2026-08-12", "2026-08-12"),
        )
        self.assertEqual(
            bot._financial_report_date_range("yesterday", today),
            ("2026-08-11", "2026-08-11"),
        )
        self.assertEqual(
            bot._financial_report_date_range("week", today),
            ("2026-08-09", "2026-08-12"),
        )
        self.assertEqual(
            bot._financial_report_date_range("month", today),
            ("2026-08-01", "2026-08-12"),
        )

    def test_custom_range_output_preserves_owner_only_treasury_visibility(self):
        summary = {
            "Date": "2026-08-01 — 2026-08-12",
            "Cash_Collected": 10000,
            "Reception_Expense": 500,
            "Reception_Handover": 7000,
            "Reception_Balance": 2500,
            "Home_Received": 7000,
            "Home_Clinic_Expense": 1000,
            "Household_Withdrawal": 2000,
            "Home_Transfer_Out": 0,
            "Home_Balance": 4000,
        }
        self.assertIn(
            "Home Treasury", bot._cash_custody_summary_text(summary, "Owner")
        )
        for role in ("Receptionist", "Manager", "Therapist"):
            self.assertNotIn(
                "Home Treasury", bot._cash_custody_summary_text(summary, role)
            )

    def test_expense_range_hides_home_treasury_rows_from_non_owner(self):
        rows = [
            {"Expense_ID": "EX1", "Category": "Small", "Amount": 100, "Type": "Clinic Expense", "Status": "Paid", "Paid_From": "Reception"},
            {"Expense_ID": "EX2", "Category": "House", "Amount": 900, "Type": "Household Withdrawal", "Status": "Paid", "Paid_From": "Home Treasury"},
        ]
        owner = bot._expense_report_text(
            rows, "2026-08-01", "2026-08-12", "Owner"
        )
        receptionist = bot._expense_report_text(
            rows, "2026-08-01", "2026-08-12", "Receptionist"
        )
        self.assertIn("EX2", owner)
        self.assertIn("Home Treasury", owner)
        self.assertNotIn("EX2", receptionist)
        self.assertNotIn("Home Treasury", receptionist)

    def test_custody_reconciliation_text_hides_home_treasury_from_non_owner(self):
        summary = {
            "Date": "2026-08-12",
            "Cash_Collected": 10000,
            "Reception_Expense": 500,
            "Reception_Handover": 7000,
            "Reception_Balance": 2500,
            "Home_Received": 7000,
            "Home_Clinic_Expense": 1000,
            "Household_Withdrawal": 2000,
            "Home_Transfer_Out": 0,
            "Home_Balance": 4000,
        }

        owner_text = bot._cash_custody_summary_text(summary, "Owner")
        self.assertIn("Home Treasury", owner_text)
        self.assertIn("Accepted receipt: ৳7000", owner_text)

        for role in ("Receptionist", "Manager", "Therapist"):
            with self.subTest(role=role):
                text = bot._cash_custody_summary_text(summary, role)
                self.assertIn("Reception", text)
                self.assertNotIn("Home Treasury", text)
                self.assertNotIn("Accepted receipt", text)
                self.assertNotIn("Household Withdrawal", text)
                self.assertNotIn("৳4000", text)


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

    def test_owner_alone_receives_separate_pt_dt_dashboard_views(self):
        dashboard_items = roles.ROLE_FINANCE_DASHBOARD_ITEMS[roles.Role.OWNER]
        for item in (
            roles.MENU_PHYSIO_FINANCE_DASHBOARD,
            roles.MENU_DENTAL_FINANCE_DASHBOARD,
        ):
            self.assertIn(item, dashboard_items)
            self.assertTrue(roles.can_access("Owner", item))
            self.assertNotIn(item, roles.ROLE_FINANCE_ITEMS[roles.Role.RECEPTIONIST])
            self.assertNotIn(item, roles.ROLE_FINANCE_ITEMS[roles.Role.MANAGER])
            self.assertFalse(roles.can_access("Receptionist", item))
            self.assertFalse(roles.can_access("Manager", item))
        self.assertNotIn(roles.MENU_COMBINED_BUSINESS_SUMMARY, dashboard_items)


class OwnerFinancialDashboardTests(unittest.TestCase):
    def test_dashboard_cash_position_ignores_closed_previous_month(self):
        summary = sheets._department_finance_summary(
            "Physio",
            "2026-08-14",
            [
                {"Date": "2026-07-31", "Department": "Physio",
                 "Amount": 200, "Payment_Method": "Cash"},
                {"Date": "2026-08-13", "Department": "Physio",
                 "Amount": 1000, "Payment_Method": "Cash"},
            ],
            [
                {"Date": "2026-07-31", "Department": "Physio",
                 "Amount": 400, "Type": "Clinic Expense", "Status": "Paid",
                 "Paid_From": "Reception"},
                {"Date": "2026-08-13", "Department": "Physio",
                 "Amount": 800, "Type": "Clinic Expense", "Status": "Paid",
                 "Paid_From": "Reception"},
            ],
            [],
            [],
        )

        self.assertEqual(summary["Closing"]["Reception"], 200)

    def test_fixed_salary_commitment_excludes_owner_and_includes_support_roles(self):
        rows = [
            {"Role": "Owner", "Status": "Active", "Salary": 99999, "Primary_Department": "All"},
            {"Role": "Therapist", "Status": "Active", "Salary": 15000, "Primary_Department": "Physio"},
            {"Role": "Cleaner", "Status": "Active", "Salary": 1300, "Primary_Department": "Physio"},
            {"Role": "Auditor", "Status": "Active", "Salary": 7500, "Primary_Department": "All", "Clinic_ID": "RELIFE-PHYSIO"},
            {"Role": "Receptionist", "Status": "Inactive", "Salary": 5000, "Primary_Department": "Physio"},
        ]
        totals = sheets._salary_commitments_for_rows(rows)
        self.assertEqual(totals["Physio"], 23800)
        self.assertEqual(totals["Dental"], 0)

    def test_dental_fixed_overhead_replaces_paid_fixed_rows_without_double_count(self):
        summary = sheets._department_finance_summary(
            "Dental",
            "2026-08-14",
            [],
            [
                {"Date": "2026-08-02", "Department": "Dental", "Category": "চেম্বার ভাড়া", "Amount": 10000, "Type": "Clinic Expense", "Status": "Paid"},
                {"Date": "2026-08-03", "Department": "Dental", "Category": "বিদ্যুৎ বিল", "Amount": 2500, "Type": "Clinic Expense", "Status": "Paid"},
                {"Date": "2026-08-04", "Department": "Dental", "Category": "Dental Lab Bill", "Amount": 4000, "Type": "Clinic Expense", "Status": "Paid"},
            ],
            [],
            [],
        )
        self.assertEqual(summary["Month_Clinic_Expense"], 16500)
        self.assertEqual(summary["Month_Variable_Clinic_Expense"], 6500)
        self.assertEqual(summary["Month_Fixed_Overhead_Actual"], 10000)
        self.assertEqual(summary["Month_Fixed_Overhead_Liability"], 19000)

    def test_dental_fixed_overhead_uses_actual_when_a_fixed_item_exceeds_budget(self):
        summary = sheets._department_finance_summary(
            "Dental",
            "2026-08-14",
            [],
            [{"Date": "2026-08-02", "Department": "Dental", "Category": "বিদ্যুৎ বিল", "Amount": 3500, "Type": "Clinic Expense", "Status": "Paid"}],
            [],
            [],
        )
        self.assertEqual(summary["Month_Fixed_Overhead_Liability"], 19000)

    def test_physio_rent_is_fixed_and_paid_rent_is_not_double_counted(self):
        summary = sheets._department_finance_summary(
            "Physio", "2026-08-14", [],
            [
                {"Date": "2026-08-02", "Department": "Physio", "Category": "চেম্বার ভাড়া", "Amount": 13000, "Type": "Clinic Expense", "Status": "Paid"},
                {"Date": "2026-08-03", "Department": "Physio", "Category": "বিদ্যুৎ বিল", "Amount": 2500, "Type": "Clinic Expense", "Status": "Paid"},
            ],
            [], [],
        )
        self.assertEqual(summary["Month_Variable_Clinic_Expense"], 2500)
        self.assertEqual(summary["Month_Fixed_Overhead_Liability"], 13000)

    def test_owner_dashboard_shows_cash_and_fixed_cost_balance(self):
        summary = {
            "Month_Salary": 8650,
            "Month_Fixed_Overhead_Commitment": 13000,
            "Month_Fixed_Overhead_Actual": 0,
            "Closing": {
                "Reception": 0,
                "Home Treasury": 10390,
                "Digital/Bank": 200,
            },
        }
        data = {
            "Date": "2026-08-14",
            "Physio": summary,
            "Dental": {"Month_Salary": 0, "Closing": {key: 0 for key in summary["Closing"]}},
            "Combined": summary,
            "Salary_Commitment": {"Physio": 64300, "Dental": 0, "Combined": 64300},
        }
        text = bot._owner_finance_view_text(data, "Combined")
        self.assertIn("বর্তমান Cash Position", text)
        self.assertIn("মোট হাতে আছে: ৳10590", text)
        self.assertIn("মোট Fixed Cost: ৳77300", text)
        self.assertIn("পরিশোধিত/অগ্রিম: ৳8650", text)
        self.assertIn("Fixed Cost বাকি: ৳68650", text)
        self.assertNotIn("collection", text)
        self.assertNotIn("Household Withdrawal", text)

    def test_dental_dashboard_uses_same_fixed_cost_payment_logic(self):
        summary = {
            "Month_Salary": 2000,
            "Month_Fixed_Overhead_Commitment": 19000,
            "Month_Fixed_Overhead_Actual": 10000,
            "Closing": {"Reception": 0, "Home Treasury": 0, "Digital/Bank": 0},
        }
        data = {
            "Date": "2026-08-14",
            "Physio": summary,
            "Dental": summary,
            "Combined": summary,
            "Salary_Commitment": {"Physio": 64300, "Dental": 23000, "Combined": 87300},
        }
        text = bot._owner_finance_view_text(data, "Dental")
        self.assertIn("মোট Fixed Cost: ৳42000", text)
        self.assertIn("পরিশোধিত/অগ্রিম: ৳12000", text)
        self.assertIn("Fixed Cost বাকি: ৳30000", text)

    def test_department_views_preserve_scope_and_opening_balances(self):
        payment_ws, expense_ws, movement_ws, salary_ws = object(), object(), object(), object()
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
            salary_ws: [
                {"Date": "2026-08-10", "Department": "Physio", "Amount": 75, "Status": "Paid", "Paid_From": "Home Treasury"},
                {"Date": "2026-08-11", "Department": "Dental", "Amount": 100, "Status": "Paid", "Paid_From": "Digital/Bank"},
            ],
        }
        with patch.object(sheets, "_worksheet", side_effect=[payment_ws, expense_ws, movement_ws, salary_ws]), patch.object(
            sheets, "safe_get_all_records", side_effect=lambda ws: records[ws]
        ):
            data = sheets.get_owner_financial_dashboard("2026-08-11")

        physio = data["Physio"]
        dental = data["Dental"]
        combined = data["Combined"]
        self.assertEqual(physio["Today_Collection"], 500)
        self.assertEqual(dental["Today_Collection"], 800)
        self.assertEqual(physio["Opening"]["Reception"], 600)
        self.assertEqual(physio["Opening"]["Home Treasury"], 325)
        self.assertEqual(physio["Closing"]["Reception"], 750)
        self.assertEqual(physio["Closing"]["Home Treasury"], 575)
        self.assertEqual(physio["Month_Salary"], 75)
        self.assertEqual(physio["Month_Net_After_Salary"], 1325)
        self.assertEqual(dental["Month_Salary"], 100)
        self.assertEqual(dental["Closing"]["Digital/Bank"], 700)
        self.assertEqual(combined["Today_Collection"], 1300)
        self.assertEqual(combined["Unclassified_Rows"]["Payments"], 1)

    def test_missing_department_never_enters_department_totals(self):
        tabs = [object(), object(), object(), object()]
        with patch.object(sheets, "_worksheet", side_effect=tabs), patch.object(
            sheets,
            "safe_get_all_records",
            side_effect=[[{"Date": "2026-08-11", "Amount": 100}], [], [], []],
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
