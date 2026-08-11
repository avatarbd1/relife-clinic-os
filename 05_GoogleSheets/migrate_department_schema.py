#!/usr/bin/env python3
"""Additive Department schema migration; dry-run and fail-closed by default."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


STAFF_SHEET = "08_Staff"
STAFF_HEADERS = [
    "Primary_Department",
    "Department_Access",
    "Clinical_Write_Scope",
    "Financial_Access",
]
MAPPING_SHEET = "Staff_Department_Access"
MAPPING_HEADERS = [
    "Mapping_ID", "Staff_ID", "Department", "Status", "Valid_From",
    "Valid_To", "Approved_By", "Approved_At", "Notes",
]

DEPARTMENT_RECORD_SHEETS = [
    "02_Patients", "04_Appointments", "Daily_Visits", "Invoices",
    "06_Payments", "05_Treatments", "10_Assessments",
    "12_Treatment_Plans", "11_Packages", "07_Expenses",
    "09_Inventory", "17_Inventory_Log",
    "14_Reports", "16_Delete_Log", "20_Data_Audit",
]

DENTAL_SHEETS = {
    "Dental_Procedures": [
        "Procedure_ID", "Patient_ID", "Visit_ID", "Department", "Tooth_Code",
        "Procedure_Code", "Procedure_Name", "Status", "Dentist_ID", "Assistant_ID",
        "Performed_At", "Author_ID", "Created_At",
    ],
    "Dental_Tooth_Chart": [
        "Chart_ID", "Patient_ID", "Department", "Tooth_Code", "Surface",
        "Finding", "Status", "Author_ID", "Recorded_At",
    ],
    "Dental_Treatment_Plans": [
        "Dental_Plan_ID", "Patient_ID", "Department", "Diagnosis", "Plan",
        "Dentist_ID", "Status", "Author_ID", "Created_At",
    ],
    "Dental_Lab_Orders": [
        "Lab_Order_ID", "Patient_ID", "Department", "Lab_Name", "Item",
        "Shade", "Order_Date", "Due_Date", "Status", "Dentist_ID", "Created_At",
    ],
    "Dental_Material_Usage": [
        "Usage_ID", "Patient_ID", "Procedure_ID", "Department", "Item_ID",
        "Quantity", "Unit", "Used_By", "Used_At",
    ],
}

CORE_NEW_SHEETS = {
    "Daily_Visits": [
        "Visit_ID", "Date", "Patient_ID", "Department", "Provider_ID",
        "Appointment_ID", "Status", "Created_At",
    ],
    "Invoices": [
        "Invoice_ID", "Date", "Patient_ID", "Department", "Visit_ID",
        "Gross_Amount", "Discount", "Net_Amount", "Paid_Amount", "Due_Amount",
        "Status", "Created_By", "Created_At",
    ],
}

CASH_MOVEMENT_HEADERS = [
    "Department", "From_Custodian_ID", "From_Staff_ID", "To_Custodian_ID",
    "Requested_Amount", "Received_Amount", "Difference", "Accepted_By",
    "Requested_At", "Accepted_At", "Completed_At", "Updated_At",
]


@dataclass(frozen=True)
class Action:
    kind: str
    sheet: str
    headers: tuple[str, ...] = ()


def _titles(book) -> set[str]:
    return {ws.title for ws in book.worksheets()}


def _missing_headers(book, sheet: str, required: list[str]) -> list[str]:
    existing = {str(value).strip() for value in book.worksheet(sheet).row_values(1)}
    return [header for header in required if header not in existing]


def plan_migration(book) -> list[Action]:
    titles = _titles(book)
    if STAFF_SHEET not in titles:
        raise RuntimeError(f"Missing required sheet: {STAFF_SHEET}")

    actions: list[Action] = []
    staff_missing = _missing_headers(book, STAFF_SHEET, STAFF_HEADERS)
    if staff_missing:
        actions.append(Action("add_headers", STAFF_SHEET, tuple(staff_missing)))

    if MAPPING_SHEET not in titles:
        actions.append(Action("create_sheet", MAPPING_SHEET, tuple(MAPPING_HEADERS)))

    for sheet, headers in {**CORE_NEW_SHEETS, **DENTAL_SHEETS}.items():
        if sheet not in titles:
            actions.append(Action("create_sheet", sheet, tuple(headers)))

    for sheet in DEPARTMENT_RECORD_SHEETS:
        if sheet not in titles:
            continue
        missing = _missing_headers(book, sheet, ["Department"])
        if missing:
            actions.append(Action("add_headers", sheet, tuple(missing)))

    if "21_Cash_Movement" in titles:
        cash_missing = _missing_headers(book, "21_Cash_Movement", CASH_MOVEMENT_HEADERS)
        if cash_missing:
            actions.append(Action("add_headers", "21_Cash_Movement", tuple(cash_missing)))
    return actions


def _append_headers(ws, headers: tuple[str, ...]) -> None:
    existing = ws.row_values(1)
    target_count = len(existing) + len(headers)
    if ws.col_count < target_count:
        ws.add_cols(target_count - ws.col_count)
    for offset, header in enumerate(headers, start=1):
        ws.update_cell(1, len(existing) + offset, header)


def migrate(
    book,
    *,
    apply: bool = False,
    backup_confirmed: bool = False,
    schema_snapshot: str = "",
) -> list[Action]:
    actions = plan_migration(book)
    if not apply:
        return actions
    if not backup_confirmed:
        raise RuntimeError("Apply blocked: full backup is not confirmed")
    snapshot = Path(schema_snapshot) if schema_snapshot else None
    if snapshot is None or not snapshot.is_file() or snapshot.stat().st_size == 0:
        raise RuntimeError("Apply blocked: a non-empty schema snapshot file is required")

    for action in actions:
        if action.kind == "create_sheet":
            ws = book.add_worksheet(action.sheet, rows=1000, cols=max(20, len(action.headers)))
            ws.append_row(list(action.headers), value_input_option="RAW")
        elif action.kind == "add_headers":
            _append_headers(book.worksheet(action.sheet), action.headers)
        else:
            raise RuntimeError(f"Unknown migration action: {action.kind}")

    remaining = plan_migration(book)
    if remaining:
        raise RuntimeError(f"Migration incomplete: {remaining}")
    return actions


def open_book(sheet_id: str):
    import gspread
    from google.oauth2.service_account import Credentials

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
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
    parser.add_argument("--backup-confirmed", action="store_true")
    parser.add_argument("--schema-snapshot", default="")
    args = parser.parse_args()
    if not args.sheet_id:
        raise SystemExit("GOOGLE_SHEET_ID or --sheet-id is required")
    actions = migrate(
        open_book(args.sheet_id),
        apply=args.apply,
        backup_confirmed=args.backup_confirmed,
        schema_snapshot=args.schema_snapshot,
    )
    print(json.dumps([asdict(action) for action in actions], indent=2))


if __name__ == "__main__":
    main()
