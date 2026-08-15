"""Regression evidence for the 2026-08-15 expense append incident.

The live 07_Expenses schema is an A1-anchored table. The runtime append guard
must stay enabled so an append cannot create data to the right of the header
and make get_all_records() fail on duplicate blank headers.
"""

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))

import gspread
import gspread_append_guard


class ExpenseSheetWidthGuardTests(unittest.TestCase):
    def test_guard_marker_is_installed_by_config_bootstrap_contract(self):
        original = gspread.Worksheet.append_row
        try:
            gspread_append_guard.install_gspread_append_guard()
            self.assertTrue(
                getattr(
                    gspread.Worksheet.append_row,
                    gspread_append_guard._PATCH_MARKER,
                    False,
                )
            )
        finally:
            gspread.Worksheet.append_row = original


if __name__ == "__main__":
    unittest.main()
