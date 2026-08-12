#!/usr/bin/env python3
"""Additive cash-custody correctness schema migration.

Dry-run is the default. Historical values are never classified or rewritten.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

REQUIRED_HEADERS = {
    "07_Expenses": ["Department"],
    "21_Cash_Movement": [
        "Department", "Requested_Amount", "Received_Amount", "Difference"
    ],
    "13_Salary": ["Department", "Paid_From", "Status", "Paid_At"],
}


def plan_migration(book) -> list[dict]:
    titles = {ws.title for ws in book.worksheets()}
    actions = []
    for title, required in REQUIRED_HEADERS.items():
        if title not in titles:
            raise RuntimeError(f"Missing required sheet: {title}")
        headers = [str(value).strip() for value in book.worksheet(title).row_values(1)]
        missing = [header for header in required if header not in headers]
        if missing:
            actions.append({"sheet": title, "add_headers": missing})
    return actions


def migrate(book, apply: bool = False) -> list[dict]:
    actions = plan_migration(book)
    if not apply:
        return actions
    for action in actions:
        ws = book.worksheet(action["sheet"])
        headers = ws.row_values(1)
        missing = action["add_headers"]
        target_count = len(headers) + len(missing)
        if ws.col_count < target_count:
            ws.add_cols(target_count - ws.col_count)
        ws.update(
            range_name=f"{gspread.utils.rowcol_to_a1(1, len(headers) + 1)}:"
            f"{gspread.utils.rowcol_to_a1(1, target_count)}",
            values=[missing],
            value_input_option="RAW",
        )
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
    parser.add_argument("--sheet-id", default=os.getenv("GOOGLE_SHEET_ID", ""))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.sheet_id:
        raise SystemExit("GOOGLE_SHEET_ID or --sheet-id is required")
    actions = migrate(open_book(args.sheet_id), apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"{mode}: {actions or ['no changes required']}")
    if actions and not args.apply:
        print("Historical rows remain blank and require explicit review.")


if __name__ == "__main__":
    main()
