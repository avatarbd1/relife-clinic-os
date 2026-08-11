#!/usr/bin/env python3
"""Additive Cash Custody Foundation migration (dry-run by default)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))
load_dotenv(ROOT / ".env")

from data_contract import UNIFIED_HEADERS  # noqa: E402

EXPENSE_SHEET = "07_Expenses"
CASH_MOVEMENT_SHEET = "21_Cash_Movement"
CASH_MOVEMENT_HEADERS = [
    "Movement_ID", "Date", "From_Custodian", "To_Custodian", "Amount",
    "Moved_By", "Note", "Timestamp",
] + UNIFIED_HEADERS + ["Status", "Confirmed_By", "Confirmed_At"]


def plan_migration(book) -> list[str]:
    titles = {ws.title for ws in book.worksheets()}
    if EXPENSE_SHEET not in titles:
        raise RuntimeError(f"Missing required sheet: {EXPENSE_SHEET}")

    expense_headers = book.worksheet(EXPENSE_SHEET).row_values(1)
    actions = []
    if "Type" not in expense_headers:
        actions.append("add_expense_type")

    if CASH_MOVEMENT_SHEET not in titles:
        actions.append("create_cash_movement")
    else:
        actual = book.worksheet(CASH_MOVEMENT_SHEET).row_values(1)
        legacy_headers = CASH_MOVEMENT_HEADERS[:-3]
        if actual[:len(legacy_headers)] != legacy_headers:
            raise RuntimeError(
                f"{CASH_MOVEMENT_SHEET} business headers do not match exactly: {actual}"
            )
        workflow_headers = CASH_MOVEMENT_HEADERS[-3:]
        actual_workflow = actual[len(legacy_headers):len(CASH_MOVEMENT_HEADERS)]
        if not actual_workflow:
            actions.append("add_cash_handover_columns")
        elif actual_workflow != workflow_headers:
            raise RuntimeError(
                f"{CASH_MOVEMENT_SHEET} handover headers do not match exactly: "
                f"{actual_workflow}"
            )
    return actions


def migrate(book, apply: bool = False) -> list[str]:
    actions = plan_migration(book)
    if not apply:
        return actions

    if "add_expense_type" in actions:
        ws = book.worksheet(EXPENSE_SHEET)
        headers = ws.row_values(1)
        if ws.col_count < len(headers) + 1:
            ws.add_cols(1)
        # Appending only the header preserves every historical row as blank.
        ws.update_cell(1, len(headers) + 1, "Type")

    if "create_cash_movement" in actions:
        ws = book.add_worksheet(
            title=CASH_MOVEMENT_SHEET,
            rows=1000,
            cols=len(CASH_MOVEMENT_HEADERS),
        )
        ws.append_row(CASH_MOVEMENT_HEADERS, value_input_option="RAW")

    if "add_cash_handover_columns" in actions:
        ws = book.worksheet(CASH_MOVEMENT_SHEET)
        headers = ws.row_values(1)
        missing_count = len(CASH_MOVEMENT_HEADERS) - len(headers)
        if missing_count > 0 and ws.col_count < len(CASH_MOVEMENT_HEADERS):
            ws.add_cols(len(CASH_MOVEMENT_HEADERS) - ws.col_count)
        for offset, header in enumerate(CASH_MOVEMENT_HEADERS[len(headers):], start=1):
            ws.update_cell(1, len(headers) + offset, header)

    # Re-plan verifies postconditions and makes repeat application a no-op.
    remaining = plan_migration(book)
    if remaining:
        raise RuntimeError(f"Migration incomplete: {remaining}")
    return actions


def open_book(sheet_id: str):
    credentials_path = os.getenv(
        "GOOGLE_CREDENTIALS_PATH", str(ROOT / "credentials.json")
    )
    credentials = Credentials.from_service_account_file(
        credentials_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(credentials).open_by_key(sheet_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--sheet-id",
        default=os.getenv("GOOGLE_SHEET_ID", ""),
        help="Target live or template spreadsheet ID (defaults to GOOGLE_SHEET_ID)",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.sheet_id:
        raise SystemExit("GOOGLE_SHEET_ID or --sheet-id is required")
    actions = migrate(open_book(args.sheet_id), apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"{mode}: {actions or ['no changes required']}")


if __name__ == "__main__":
    main()
