"""Cash custody correctness: salary outflow, Bank, in-transit, Paid_At, Unclassified.

Also guards the missing-module-import bug that crashed every scoped finance read:
`sheets.py` referenced `department_access.<name>` while only importing two names
from that module, so any non-empty department scope raised NameError.
"""
import ast
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

import sheets  # noqa: E402
import config  # noqa: E402


def tearDownModule():
    if _CREATED_CREDENTIALS:
        _CREDENTIALS.unlink(missing_ok=True)


class ModuleImportRegressionTests(unittest.TestCase):
    """These calls raised NameError before the module import was added."""

    def test_department_access_is_imported_as_a_module(self):
        self.assertTrue(hasattr(sheets, "department_access"))

    def test_scope_values_resolve_without_a_name_error(self):
        self.assertEqual(
            sorted(sheets._department_scope_values(["All"])),
            [config.DEPARTMENT_DENTAL, config.DEPARTMENT_PHYSIO],
        )

    def test_inventory_department_resolves_without_a_name_error(self):
        self.assertEqual(
            sheets._inventory_department(config.DEPARTMENT_PHYSIO),
            config.DEPARTMENT_PHYSIO,
        )

    def test_filter_drops_only_rows_outside_the_scope(self):
        rows = [
            {"Department": config.DEPARTMENT_PHYSIO},
            {"Department": ""},
        ]
        self.assertEqual(
            sheets.filter_records_by_departments(rows, ["All"]),
            [{"Department": config.DEPARTMENT_PHYSIO}],
        )


class CashDateSelectionTests(unittest.TestCase):
    def test_effective_date_prefers_when_the_cash_actually_left(self):
        self.assertEqual(
            sheets._cash_effective_date(
                {"Date": "2026-08-01", "Paid_At": "2026-08-05 03:00 PM"}
            ),
            "2026-08-05",
        )

    def test_effective_date_falls_back_to_date_for_legacy_rows(self):
        self.assertEqual(
            sheets._cash_effective_date({"Date": "2026-08-01", "Paid_At": ""}),
            "2026-08-01",
        )

    def test_blank_dates_are_never_in_range(self):
        self.assertFalse(sheets._in_range("", "2026-08-01", "2026-08-31"))


class UnclassifiedDetectionTests(unittest.TestCase):
    def test_missing_department_counts_as_unclassified(self):
        self.assertTrue(sheets._is_unclassified({"Department": ""}))

    def test_known_department_is_not_unclassified(self):
        self.assertFalse(
            sheets._is_unclassified({"Department": config.DEPARTMENT_PHYSIO})
        )


class SalaryCustodyCaptureTests(unittest.TestCase):
    """Salary must record which custodian the cash left."""

    def source(self, name):
        tree = ast.parse((BOT_DIR / "sheets.py").read_text(encoding="utf-8"))
        node = next(
            item for item in ast.walk(tree)
            if isinstance(item, ast.FunctionDef) and item.name == name
        )
        return ast.unparse(node)

    def test_writer_accepts_and_validates_a_custodian(self):
        body = self.source("add_salary_payment")
        self.assertIn("paid_from", body)
        self.assertIn("CASH_CUSTODIANS", body)
        self.assertIn("Paid_At", body)

    def test_writer_refuses_an_unknown_custodian(self):
        with self.assertRaises(ValueError):
            sheets.add_salary_payment(
                "ST01", "2026-08", 100, paid_by="x", paid_from="Pocket"
            )

    def test_checked_writer_forwards_the_custodian(self):
        self.assertIn("paid_from=paid_from", self.source("add_salary_payment_checked"))


class CustodySummaryShapeTests(unittest.TestCase):
    """Every custodian in config must have a balance line in the summary."""

    def test_summary_reports_each_configured_custodian(self):
        body = ast.unparse(
            next(
                item for item in ast.walk(
                    ast.parse((BOT_DIR / "sheets.py").read_text(encoding="utf-8"))
                )
                if isinstance(item, ast.FunctionDef)
                and item.name == "get_cash_custody_summary"
            )
        )
        for key in (
            "Reception_Balance", "Home_Balance", "Bank_Balance",
            "Reception_Salary", "Home_Salary", "Bank_Salary",
            "Reception_In_Transit", "Home_In_Transit",
            "Unclassified_Total",
        ):
            with self.subTest(key=key):
                self.assertIn(key, body)

    def test_salary_is_subtracted_from_each_balance(self):
        body = ast.unparse(
            next(
                item for item in ast.walk(
                    ast.parse((BOT_DIR / "sheets.py").read_text(encoding="utf-8"))
                )
                if isinstance(item, ast.FunctionDef)
                and item.name == "get_cash_custody_summary"
            )
        )
        self.assertIn("cash_collected - reception_expense - reception_salary", body)
        self.assertIn("home_salary", body)
        self.assertIn("bank_salary", body)

    def test_movement_totals_use_the_received_amount_helper(self):
        body = ast.unparse(
            next(
                item for item in ast.walk(
                    ast.parse((BOT_DIR / "sheets.py").read_text(encoding="utf-8"))
                )
                if isinstance(item, ast.FunctionDef)
                and item.name == "get_cash_custody_summary"
            )
        )
        self.assertIn("_movement_amount(row)", body)


class ReportVisibilityTests(unittest.TestCase):
    """Payroll and treasury detail stay Owner-only."""

    def source(self):
        tree = ast.parse((BOT_DIR / "bot.py").read_text(encoding="utf-8"))
        node = next(
            item for item in ast.walk(tree)
            if isinstance(item, ast.FunctionDef)
            and item.name == "_cash_custody_summary_text"
        )
        return ast.unparse(node)

    def test_bank_and_unclassified_blocks_are_owner_only(self):
        body = self.source()
        owner_section = body[body.index("if is_owner:"):]
        for key in ("Bank_Balance", "Home_Balance", "Unclassified_Total"):
            with self.subTest(key=key):
                self.assertIn(key, owner_section)

    def test_non_owner_sees_reception_salary_without_the_payroll_label(self):
        body = self.source()
        shared_section = body[:body.index("if is_owner:")]
        self.assertIn("Reception_Salary", shared_section)
        self.assertIn("অন্যান্য নগদ পরিশোধ", shared_section)


if __name__ == "__main__":
    unittest.main()
