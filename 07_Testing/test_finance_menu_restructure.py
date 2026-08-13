"""Owner's চলতি হিসাব restructure (13 buttons -> 4 grouped tabs) and the new
❌ প্রত্যাখ্যাত খরচ (Rejected Expenses) view, split out of ক্লিনিক খরচ হিসাব.
"""
import os
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "test-token")
os.environ.setdefault("GOOGLE_SHEET_ID", "test-sheet")

_CREDENTIALS = ROOT / "credentials.json"
_CREATED_CREDENTIALS = False
if not _CREDENTIALS.exists():
    _CREDENTIALS.write_text("{}", encoding="utf-8")
    _CREATED_CREDENTIALS = True

import roles  # noqa: E402
import bot  # noqa: E402


def tearDownModule():
    if _CREATED_CREDENTIALS:
        _CREDENTIALS.unlink(missing_ok=True)


class OwnerFinanceTopLevelTests(unittest.TestCase):
    def test_owner_top_level_has_exactly_four_tabs(self):
        self.assertEqual(
            roles.ROLE_FINANCE_ITEMS[roles.Role.OWNER],
            [
                roles.MENU_CUSTODY_BALANCE,
                roles.MENU_FINANCE_DASHBOARDS,
                roles.MENU_FINANCE_ACCOUNTS,
                roles.MENU_HOUSEHOLD_WITHDRAWAL,
            ],
        )

    def test_receptionist_and_manager_menus_unchanged_in_shape(self):
        # Only gains Rejected Expenses; still a flat list, not restructured.
        self.assertIn(
            roles.MENU_REJECTED_EXPENSES,
            roles.ROLE_FINANCE_ITEMS[roles.Role.RECEPTIONIST],
        )
        self.assertIn(
            roles.MENU_REJECTED_EXPENSES,
            roles.ROLE_FINANCE_ITEMS[roles.Role.MANAGER],
        )


class DashboardGroupTests(unittest.TestCase):
    def test_dashboard_group_has_the_three_dashboard_views(self):
        items = roles.ROLE_FINANCE_DASHBOARD_ITEMS[roles.Role.OWNER]
        self.assertEqual(
            items,
            [
                roles.MENU_PHYSIO_FINANCE_DASHBOARD,
                roles.MENU_DENTAL_FINANCE_DASHBOARD,
                roles.MENU_COMBINED_BUSINESS_SUMMARY,
            ],
        )

    def test_only_owner_has_a_dashboard_group(self):
        self.assertNotIn(roles.Role.RECEPTIONIST, roles.ROLE_FINANCE_DASHBOARD_ITEMS)
        self.assertNotIn(roles.Role.MANAGER, roles.ROLE_FINANCE_DASHBOARD_ITEMS)


class AccountsGroupTests(unittest.TestCase):
    def test_accounts_group_has_the_nine_moved_items(self):
        items = roles.ROLE_FINANCE_ACCOUNTS_ITEMS[roles.Role.OWNER]
        for item in (
            roles.MENU_SALARY, roles.MENU_SALARY_HISTORY, roles.MENU_MY_PAYMENTS,
            roles.MENU_OWNER_CLINIC_EXPENSE, roles.MENU_EXPENSE_APPROVAL,
            roles.MENU_EXPENSE_TRACKER, roles.MENU_REJECTED_EXPENSES,
            roles.MENU_CASH_RECEIVE, roles.MENU_CASH_MOVEMENTS,
        ):
            with self.subTest(item=item):
                self.assertIn(item, items)

    def test_household_withdrawal_stays_at_top_level_not_in_accounts(self):
        self.assertNotIn(
            roles.MENU_HOUSEHOLD_WITHDRAWAL,
            roles.ROLE_FINANCE_ACCOUNTS_ITEMS[roles.Role.OWNER],
        )


class PermissionsStillWorkTests(unittest.TestCase):
    """Moving buttons between menus must not change who can actually use them."""

    def test_owner_can_still_reach_every_moved_item(self):
        for item in (
            roles.MENU_PHYSIO_FINANCE_DASHBOARD, roles.MENU_DENTAL_FINANCE_DASHBOARD,
            roles.MENU_COMBINED_BUSINESS_SUMMARY, roles.MENU_SALARY,
            roles.MENU_SALARY_HISTORY, roles.MENU_MY_PAYMENTS,
            roles.MENU_OWNER_CLINIC_EXPENSE, roles.MENU_HOUSEHOLD_WITHDRAWAL,
            roles.MENU_EXPENSE_APPROVAL, roles.MENU_EXPENSE_TRACKER,
            roles.MENU_CASH_RECEIVE, roles.MENU_CASH_MOVEMENTS,
            roles.MENU_CUSTODY_BALANCE, roles.MENU_REJECTED_EXPENSES,
        ):
            with self.subTest(item=item):
                self.assertTrue(roles.can_access("Owner", item))

    def test_receptionist_and_manager_can_reach_rejected_expenses(self):
        self.assertTrue(roles.can_access("Receptionist", roles.MENU_REJECTED_EXPENSES))
        self.assertTrue(roles.can_access("Manager", roles.MENU_REJECTED_EXPENSES))

    def test_therapist_still_has_no_finance_access(self):
        self.assertFalse(roles.can_access("Therapist", roles.MENU_REJECTED_EXPENSES))
        self.assertFalse(roles.can_access("Therapist", roles.MENU_CUSTODY_BALANCE))


class RejectedExpenseReportTests(unittest.TestCase):
    def test_rejected_rows_excluded_from_the_default_expense_report(self):
        rows = [
            {"Expense_ID": "EX01", "Category": "ভাড়া", "Amount": 1000,
             "Status": "Paid", "Type": "Clinic", "Paid_From": "Reception"},
            {"Expense_ID": "EX02", "Category": "মার্কেটিং", "Amount": 5000,
             "Status": "Rejected", "Type": "Clinic", "Paid_From": "Reception"},
        ]
        text = bot._expense_report_text(rows, "2026-08-01", "2026-08-14", "Owner")
        self.assertIn("EX01", text)
        self.assertNotIn("EX02", text)
        self.assertNotIn("Rejected", text)

    def test_rejected_report_shows_only_rejected_rows(self):
        rows = [
            {"Expense_ID": "EX02", "Category": "মার্কেটিং", "Amount": 5000,
             "Paid_From": "Reception", "Approved_By": ""},
        ]
        text = bot._rejected_expense_report_text(rows, "2026-08-01", "2026-08-14")
        self.assertIn("EX02", text)
        self.assertIn("প্রত্যাখ্যাত খরচ", text)

    def test_rejected_report_handles_empty_range(self):
        text = bot._rejected_expense_report_text([], "2026-08-14", "2026-08-14")
        self.assertIn("কোনো প্রত্যাখ্যাত খরচ নেই", text)

    def test_rejected_menu_is_registered_for_authorization(self):
        self.assertEqual(
            bot._FINANCIAL_REPORT_MENUS["rejected"], roles.MENU_REJECTED_EXPENSES
        )


if __name__ == "__main__":
    unittest.main()
