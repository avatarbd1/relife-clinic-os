#!/usr/bin/env python3
"""One-time, additive migration for Relife Unified Data Architecture v1.

Dry-run is the default.  Use --apply to append metadata columns, backfill safe
identity/provenance values, and create empty consent/audit ledgers.  Existing
columns and values are never deleted or reordered.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials


ROOT = Path(__file__).resolve().parents[1]
BOT_DIR = ROOT / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
load_dotenv(ROOT / ".env")

from data_contract import (  # noqa: E402
    BRANCH_ID,
    CLINIC_ID,
    ORGANIZATION_ID,
    SCHEMA_VERSION,
    UNIFIED_HEADERS,
    encounter_id_from_treatment,
)


CORE_SHEETS = [
    "02_Patients", "03_Attendance", "04_Appointments", "05_Treatments",
    "06_Payments", "07_Expenses", "08_Staff", "09_Inventory",
    "10_Assessments", "11_Packages", "12_Treatment_Plans", "13_Salary",
    "14_Reports", "15_Case_Studies", "16_Delete_Log", "17_Inventory_Log",
    "18_Learning_Progress",
]

CONSENT_HEADERS = [
    "Consent_ID", "Patient_ID", "Purpose", "Status", "Consent_Version",
    "Recorded_By", "Recorded_At", "Withdrawn_At", "Notes",
] + UNIFIED_HEADERS

AUDIT_HEADERS = [
    "Audit_ID", "Timestamp", "Actor_ID", "Action", "Entity_Type",
    "Entity_ID", "Patient_ID", "Before_Value", "After_Value", "Reason",
] + UNIFIED_HEADERS


def _client():
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", str(ROOT / "credentials.json"))
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID is missing")
    if not Path(credentials_path).exists():
        raise RuntimeError(f"Credentials file is missing: {credentials_path}")
    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    return gspread.authorize(creds).open_by_key(sheet_id)


def _planned_headers(ws) -> list[str]:
    existing = ws.row_values(1)
    return [h for h in UNIFIED_HEADERS if h not in existing]


def _backfill(ws) -> int:
    values = ws.get_all_values()
    if len(values) <= 1:
        return 0
    headers = values[0]
    updates = []
    for row_number, row in enumerate(values[1:], start=2):
        if not any(row):
            continue
        first_id = row[0].strip() if row else ""
        safe_defaults = {
            "Organization_ID": ORGANIZATION_ID,
            "Clinic_ID": CLINIC_ID,
            "Branch_ID": BRANCH_ID,
            "Record_ID": f"{CLINIC_ID}:{first_id}" if first_id else "",
            "Encounter_ID": encounter_id_from_treatment(first_id) if ws.title == "05_Treatments" and first_id else "",
            "Source_System": "legacy_sheet",
            "Source_Type": "legacy_record",
            "AI_Generated": "FALSE",
            # Historical records were not collected under this verification contract.
            "Human_Verified": "FALSE",
            "Schema_Version": SCHEMA_VERSION,
        }
        for header, value in safe_defaults.items():
            col = headers.index(header) + 1
            current = row[col - 1] if len(row) >= col else ""
            if not current and value != "":
                updates.append({"range": gspread.utils.rowcol_to_a1(row_number, col), "values": [[value]]})
    for start in range(0, len(updates), 500):
        ws.batch_update(updates[start:start + 500], value_input_option="RAW")
    return len(updates)


def run(apply: bool) -> None:
    book = _client()
    existing_titles = {ws.title for ws in book.worksheets()}
    for title in CORE_SHEETS:
        if title not in existing_titles:
            print(f"SKIP {title}: sheet not found")
            continue
        ws = book.worksheet(title)
        additions = _planned_headers(ws)
        print(f"{title}: add {len(additions)} unified columns")
        if apply and additions:
            current = ws.row_values(1)
            required_cols = len(current) + len(additions)
            if ws.col_count < required_cols:
                ws.add_cols(required_cols - ws.col_count)
            ws.update(range_name="A1", values=[current + additions], value_input_option="RAW")
        if apply:
            print(f"  backfilled cells: {_backfill(ws)}")

    ledgers = {
        "19_Consent": CONSENT_HEADERS,
        "20_Data_Audit": AUDIT_HEADERS,
    }
    for title, headers in ledgers.items():
        if title in existing_titles:
            print(f"{title}: already exists")
        elif apply:
            ws = book.add_worksheet(title=title, rows=1000, cols=len(headers))
            ws.append_row(headers, value_input_option="RAW")
            print(f"{title}: created")
        else:
            print(f"{title}: would create")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply additive changes (default is dry-run)")
    args = parser.parse_args()
    run(args.apply)
