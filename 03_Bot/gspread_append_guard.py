"""Relife guard for stable Google Sheets row appends.

Google Sheets values.append can choose a different logical table when the
request range is the whole worksheet. Relife sheets are canonical A1 tables,
so force gspread append_row() calls without an explicit table_range to anchor
at A1. Callers that already provide table_range keep their own value.
"""

from __future__ import annotations

from functools import wraps

import gspread


_PATCH_MARKER = "_relife_a1_append_guard"


def install_gspread_append_guard() -> None:
    original = gspread.Worksheet.append_row
    if getattr(original, _PATCH_MARKER, False):
        return

    @wraps(original)
    def anchored_append_row(
        self,
        values,
        value_input_option="RAW",
        insert_data_option=None,
        table_range=None,
        include_values_in_response=False,
    ):
        return original(
            self,
            values,
            value_input_option=value_input_option,
            insert_data_option=insert_data_option,
            table_range=table_range or "A1",
            include_values_in_response=include_values_in_response,
        )

    setattr(anchored_append_row, _PATCH_MARKER, True)
    gspread.Worksheet.append_row = anchored_append_row
