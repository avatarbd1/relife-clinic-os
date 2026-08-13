"""get_reception_cash_balance(): the auto-suggested amount shown when a
receptionist opens Cash Handover, replacing the old static "5000" example.

Reuses get_cash_custody_summary()'s already-tested Reception_Balance math,
called over the full record history instead of just "today" — so it behaves
as a running/carry-forward balance rather than a single-day movement.
"""
import ast
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


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


def _fake_records_by_sheet(rows_by_sheet):
    def _read(ws, *args, **kwargs):
        return list(rows_by_sheet.get(ws, []))
    return _read


class ReceptionCashBalanceTests(unittest.TestCase):
    def test_balance_spans_full_history_not_just_today(self):
        rows = {
            config.SHEET_PAYMENTS: [
                {
                    "Date": "2026-01-01", "Payment_Method": "Cash",
                    "Amount": 1000, "Department": config.DEPARTMENT_PHYSIO,
                },
            ],
            config.SHEET_EXPENSES: [
                {
                    "Paid_At": "2026-01-02", "Paid_From": config.CASH_CUSTODIAN_RECEPTION,
                    "Amount": 300, "Status": "Paid", "Department": config.DEPARTMENT_PHYSIO,
                },
            ],
            config.SHEET_CASH_MOVEMENT: [
                {
                    "Date": "2026-01-03", "Status": "Accepted",
                    "From_Custodian": config.CASH_CUSTODIAN_RECEPTION,
                    "To_Custodian": config.CASH_CUSTODIAN_HOME_TREASURY,
                    "Amount": 200, "Department": config.DEPARTMENT_PHYSIO,
                },
            ],
            config.SHEET_SALARY: [],
        }
        with patch.object(sheets, "_worksheet", side_effect=lambda name: name), \
             patch.object(sheets, "safe_get_all_records", side_effect=_fake_records_by_sheet(rows)):
            balance = sheets.get_reception_cash_balance(config.DEPARTMENT_PHYSIO)
        # 1000 collected - 300 paid expense - 200 accepted handover out
        self.assertEqual(balance, 500)

    def test_zero_when_nothing_recorded(self):
        with patch.object(sheets, "_worksheet", side_effect=lambda name: name), \
             patch.object(sheets, "safe_get_all_records", return_value=[]):
            self.assertEqual(sheets.get_reception_cash_balance(config.DEPARTMENT_DENTAL), 0)

    def test_scoped_to_the_requested_department_only(self):
        rows = {
            config.SHEET_PAYMENTS: [
                {
                    "Date": "2026-01-01", "Payment_Method": "Cash",
                    "Amount": 500, "Department": config.DEPARTMENT_PHYSIO,
                },
                {
                    "Date": "2026-01-01", "Payment_Method": "Cash",
                    "Amount": 900, "Department": config.DEPARTMENT_DENTAL,
                },
            ],
            config.SHEET_EXPENSES: [],
            config.SHEET_CASH_MOVEMENT: [],
            config.SHEET_SALARY: [],
        }
        with patch.object(sheets, "_worksheet", side_effect=lambda name: name), \
             patch.object(sheets, "safe_get_all_records", side_effect=_fake_records_by_sheet(rows)):
            self.assertEqual(sheets.get_reception_cash_balance(config.DEPARTMENT_PHYSIO), 500)


class HandoverPromptWiringTests(unittest.TestCase):
    """cash_department_callback must use the computed balance, with a safe fallback."""

    def source(self):
        tree = ast.parse((BOT_DIR / "bot.py").read_text(encoding="utf-8"))
        node = next(
            item for item in ast.walk(tree)
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == "cash_department_callback"
        )
        return ast.unparse(node)

    def test_calls_the_balance_helper(self):
        self.assertIn("get_reception_cash_balance", self.source())

    def test_falls_back_to_manual_entry_on_error(self):
        body = self.source()
        self.assertIn("except Exception", body)
        self.assertIn("শুধু টাকার পরিমাণ লেখো", body)

    def test_suggested_amount_is_never_negative(self):
        self.assertIn("max(0, round(balance))", self.source())


if __name__ == "__main__":
    unittest.main()
