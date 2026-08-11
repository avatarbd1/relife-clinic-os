#!/usr/bin/env python3
"""Read-only Department migration audit.

This tool never mutates a spreadsheet. It inventories required tabs, headers,
and row classifications so ambiguous data can be reviewed before enforcement.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, field


DEPARTMENT_PHYSIO = "Physio"
DEPARTMENT_DENTAL = "Dental"
DEPARTMENT_ALL = "All"
CLINICAL_DEPARTMENTS = {DEPARTMENT_PHYSIO, DEPARTMENT_DENTAL}

STAFF_SHEET = "08_Staff"
STAFF_REQUIRED_HEADERS = {
    "Primary_Department",
    "Department_Access",
    "Clinical_Write_Scope",
    "Financial_Access",
}
MAPPING_SHEET = "Staff_Department_Access"

# Names are explicit contracts. Missing proposed tabs are reported, not created.
REQUIRED_RECORD_SHEETS = (
    "02_Patients",
    "04_Appointments",
    "Daily_Visits",
    "Invoices",
    "06_Payments",
    "05_Treatments",
    "10_Assessments",
    "12_Treatment_Plans",
    "11_Packages",
    "07_Expenses",
    "21_Cash_Movement",
    "09_Inventory",
    "17_Inventory_Log",
    "14_Reports",
    "16_Delete_Log",
    "20_Data_Audit",
    "Dental_Procedures",
    "Dental_Tooth_Chart",
    "Dental_Treatment_Plans",
    "Dental_Lab_Orders",
    "Dental_Material_Usage",
)


@dataclass
class SheetAudit:
    sheet: str
    present: bool
    row_count: int = 0
    department_header: bool = False
    valid_rows: int = 0
    missing_department_rows: list[int] = field(default_factory=list)
    invalid_department_rows: list[int] = field(default_factory=list)
    department_counts: dict[str, int] = field(default_factory=dict)

    @property
    def unclassified_count(self) -> int:
        return len(self.missing_department_rows) + len(self.invalid_department_rows)


def _headers(ws) -> list[str]:
    return [str(value).strip() for value in ws.row_values(1)]


def _records(ws) -> list[dict]:
    return list(ws.get_all_records()) if getattr(ws, "row_count", 2) >= 2 else []


def audit_record_sheet(book, title: str) -> SheetAudit:
    titles = {ws.title for ws in book.worksheets()}
    if title not in titles:
        return SheetAudit(sheet=title, present=False)

    ws = book.worksheet(title)
    headers = _headers(ws)
    records = _records(ws)
    result = SheetAudit(
        sheet=title,
        present=True,
        row_count=len(records),
        department_header="Department" in headers,
    )
    if not result.department_header:
        result.missing_department_rows = list(range(2, len(records) + 2))
        return result

    for row_number, row in enumerate(records, start=2):
        raw = str(row.get("Department", "")).strip()
        if not raw:
            result.missing_department_rows.append(row_number)
        elif raw not in CLINICAL_DEPARTMENTS:
            result.invalid_department_rows.append(row_number)
        else:
            result.valid_rows += 1
            result.department_counts[raw] = result.department_counts.get(raw, 0) + 1
    return result


def audit_department_schema(book) -> dict:
    titles = {ws.title for ws in book.worksheets()}
    staff_headers = _headers(book.worksheet(STAFF_SHEET)) if STAFF_SHEET in titles else []
    sheet_results = [audit_record_sheet(book, title) for title in REQUIRED_RECORD_SHEETS]
    unclassified = sum(item.unclassified_count for item in sheet_results)
    missing_tabs = [item.sheet for item in sheet_results if not item.present]
    missing_headers = [
        item.sheet for item in sheet_results if item.present and not item.department_header
    ]
    return {
        "mode": "read_only",
        "enforcement_ready": (
            STAFF_SHEET in titles
            and MAPPING_SHEET in titles
            and STAFF_REQUIRED_HEADERS.issubset(staff_headers)
            and not missing_tabs
            and not missing_headers
            and unclassified == 0
        ),
        "staff_sheet_present": STAFF_SHEET in titles,
        "staff_missing_headers": sorted(STAFF_REQUIRED_HEADERS.difference(staff_headers)),
        "mapping_sheet_present": MAPPING_SHEET in titles,
        "missing_tabs": missing_tabs,
        "missing_department_headers": missing_headers,
        "unclassified_count": unclassified,
        "sheets": [asdict(item) | {"unclassified_count": item.unclassified_count} for item in sheet_results],
    }


def open_book(sheet_id: str):
    import gspread
    from google.oauth2.service_account import Credentials

    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    credentials = Credentials.from_service_account_file(
        credentials_path,
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(credentials).open_by_key(sheet_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet-id", default=os.getenv("GOOGLE_SHEET_ID", ""))
    args = parser.parse_args()
    if not args.sheet_id:
        raise SystemExit("GOOGLE_SHEET_ID or --sheet-id is required")
    print(json.dumps(audit_department_schema(open_book(args.sheet_id)), indent=2))


if __name__ == "__main__":
    main()
