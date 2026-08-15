import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))

import gspread
import gspread_append_guard


class GspreadAppendGuardTests(unittest.TestCase):
    def setUp(self):
        self.real_append_row = gspread.Worksheet.append_row
        self.calls = []

        def fake_append_row(
            worksheet,
            values,
            value_input_option="RAW",
            insert_data_option=None,
            table_range=None,
            include_values_in_response=False,
        ):
            self.calls.append(
                {
                    "values": values,
                    "value_input_option": value_input_option,
                    "insert_data_option": insert_data_option,
                    "table_range": table_range,
                    "include_values_in_response": include_values_in_response,
                }
            )
            return {"ok": True}

        gspread.Worksheet.append_row = fake_append_row
        gspread_append_guard.install_gspread_append_guard()

    def tearDown(self):
        gspread.Worksheet.append_row = self.real_append_row

    def test_missing_table_range_is_anchored_to_a1(self):
        result = gspread.Worksheet.append_row(object(), ["EX0001", "2026-08-15"])
        self.assertEqual(result, {"ok": True})
        self.assertEqual(self.calls[-1]["table_range"], "A1")

    def test_explicit_table_range_is_preserved(self):
        gspread.Worksheet.append_row(
            object(),
            ["x"],
            table_range="B2:D20",
        )
        self.assertEqual(self.calls[-1]["table_range"], "B2:D20")

    def test_install_is_idempotent(self):
        first = gspread.Worksheet.append_row
        gspread_append_guard.install_gspread_append_guard()
        self.assertIs(gspread.Worksheet.append_row, first)


if __name__ == "__main__":
    unittest.main()
