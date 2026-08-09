#!/usr/bin/env python3
"""Read-only structural audit for the Relife Clinic OS Google workbook.

The command reports counts and schema defects only. It never prints cell
contents and never calls a mutating Google Sheets method.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path


CORE_SHEETS = [
    "02_Patients", "03_Attendance", "04_Appointments", "05_Treatments",
    "06_Payments", "07_Expenses", "08_Staff", "09_Inventory",
    "10_Assessments", "11_Packages", "12_Treatment_Plans", "13_Salary",
    "14_Reports", "15_Case_Studies", "16_Delete_Log", "17_Inventory_Log",
    "18_Learning_Progress", "19_Consent", "20_Data_Audit",
]

UNIFIED_HEADERS = [
    "Organization_ID", "Clinic_ID", "Branch_ID", "Record_ID",
    "Encounter_ID", "Provider_ID", "Source_System", "Source_Type",
    "AI_Generated", "Human_Verified", "Schema_Version",
    "Provenance_Timestamp",
]

FORMULA_ERRORS = {"#REF!", "#VALUE!", "#N/A", "#DIV/0!", "#NAME?", "#NUM!"}


def audit_values(title: str, values: list[list[str]]) -> dict:
    """Return structural findings without exposing any workbook values."""
    if not values:
        return {
            "sheet": title,
            "status": "EMPTY",
            "rows": 0,
            "columns": 0,
            "blank_headers": 0,
            "duplicate_headers": [],
            "missing_unified_headers": list(UNIFIED_HEADERS),
            "rows_wider_than_header": 0,
            "duplicate_primary_ids": 0,
            "formula_errors": 0,
        }

    headers = [str(value).strip() for value in values[0]]
    nonblank = [header for header in headers if header]
    duplicate_headers = sorted(
        header for header, count in Counter(nonblank).items() if count > 1
    )
    data_rows = [row for row in values[1:] if any(str(cell).strip() for cell in row)]
    rows_wider = sum(len(row) > len(headers) for row in data_rows)

    primary_index = next(
        (index for index, header in enumerate(headers) if header.endswith("_ID")),
        None,
    )
    primary_ids: list[str] = []
    if primary_index is not None:
        primary_ids = [
            str(row[primary_index]).strip()
            for row in data_rows
            if len(row) > primary_index and str(row[primary_index]).strip()
        ]
    duplicate_primary_ids = sum(
        count - 1 for count in Counter(primary_ids).values() if count > 1
    )

    formula_errors = sum(
        str(cell).strip().upper() in FORMULA_ERRORS
        for row in data_rows
        for cell in row
    )
    missing_unified = [header for header in UNIFIED_HEADERS if header not in headers]
    has_defect = bool(
        not headers
        or any(not header for header in headers)
        or duplicate_headers
        or rows_wider
        or duplicate_primary_ids
        or formula_errors
        or missing_unified
    )
    return {
        "sheet": title,
        "status": "REVIEW" if has_defect else "OK",
        "rows": len(data_rows),
        "columns": len(headers),
        "blank_headers": sum(not header for header in headers),
        "duplicate_headers": duplicate_headers,
        "missing_unified_headers": missing_unified,
        "rows_wider_than_header": rows_wider,
        "duplicate_primary_ids": duplicate_primary_ids,
        "formula_errors": formula_errors,
    }


def open_workbook():
    import gspread
    from dotenv import load_dotenv
    from google.oauth2.service_account import Credentials

    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
    credentials_path = Path(
        os.getenv("GOOGLE_CREDENTIALS_PATH", str(root / "credentials.json"))
    )
    if not sheet_id:
        raise RuntimeError("GOOGLE_SHEET_ID is missing")
    if not credentials_path.exists():
        raise RuntimeError(f"Credentials file is missing: {credentials_path}")
    credentials = Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return gspread.authorize(credentials).open_by_key(sheet_id)


def run() -> dict:
    workbook = open_workbook()
    worksheets = {worksheet.title: worksheet for worksheet in workbook.worksheets()}
    missing = [title for title in CORE_SHEETS if title not in worksheets]
    results = [
        audit_values(title, worksheets[title].get_all_values())
        for title in CORE_SHEETS
        if title in worksheets
    ]
    return {
        "mode": "read_only",
        "expected_sheet_count": len(CORE_SHEETS),
        "found_sheet_count": len(results),
        "missing_sheets": missing,
        "sheets": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    report = run()
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Audit report written: {args.output}")
    else:
        print(rendered)
    defects = bool(report["missing_sheets"]) or any(
        sheet["status"] != "OK" for sheet in report["sheets"]
    )
    return 1 if defects else 0


if __name__ == "__main__":
    raise SystemExit(main())
