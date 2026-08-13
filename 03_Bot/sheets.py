"""
sheets.py
Google Sheets-কে ডেটাবেস হিসেবে ব্যবহার করার জন্য gspread wrapper।
সব read/write এই ফাইলের মধ্য দিয়ে যাবে — bot.py সরাসরি gspread ছুঁবে না,
এতে ভবিষ্যতে ডেটাবেস বদলাতে হলে (যেমন Postgres-এ migrate) শুধু এই ফাইলটাই বদলালেই হবে।
"""

import json
import gspread
import re
import os
import random

import time
import threading

import config
import department_access
import sheet_scope
from department_access import AccessAction, authorize_record
from tenant_runtime import current_tenant
from gspread.http_client import HTTPClient
from gspread.utils import numericise_all, rowcol_to_a1, to_records


def _safe_float(value):
    """শীট থেকে আসা মান (খালি স্ট্রিং, কমাযুক্ত সংখ্যা, N/A ইত্যাদি) নিরাপদে float-এ কনভার্ট করে।
    ব্যর্থ হলে 0.0 রিটার্ন করে, কখনো crash করে না।"""
    if value is None:
        return 0.0
    try:
        cleaned = str(value).replace("৳", "").replace(",", "").strip()
        if cleaned == "" or cleaned.upper() == "N/A":
            return 0.0
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0


def _safe_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


_records_cache = {}  # {(spreadsheet_id, worksheet_id): (timestamp, records)}
_records_cache_lock = threading.RLock()
_records_cache_generation: dict[tuple[str, int | str], int] = {}
_RECORDS_CACHE_TTL = max(
    0.0, float(os.getenv("SHEETS_RECORDS_CACHE_TTL_SECONDS", "10"))
)


def _active_sheet_id() -> str:
    override = sheet_scope.current_sheet_override()
    if override:
        return override
    if config.MULTITENANT_ENABLED:
        return current_tenant().sheet_id
    return config.GOOGLE_SHEET_ID


def _worksheet_sheet_id(ws) -> str:
    sheet_id = getattr(ws, "spreadsheet_id", None)
    if not sheet_id:
        sheet_id = getattr(getattr(ws, "spreadsheet", None), "id", None)
    if not sheet_id:
        raise RuntimeError("Cannot verify worksheet spreadsheet identity")
    return str(sheet_id)


def _assert_current_worksheet(ws) -> str:
    actual = _worksheet_sheet_id(ws)
    expected = str(_active_sheet_id())
    if actual != expected:
        raise RuntimeError(
            f"Tenant isolation violation: expected sheet {expected}, got {actual}"
        )
    return actual


def _records_cache_key(ws) -> tuple[str, int | str]:
    return (_assert_current_worksheet(ws), getattr(ws, "id", ws.title))


def safe_get_all_records(
    ws,
    _retries: int = 2,
    _use_cache: bool = True,
    _race_retries: int = 2,
):
    """get_all_records()-এর নিরাপদ ভার্সন — sheet-এ শুধু header বা কোনো row না থাকলে crash না করে খালি list রিটার্ন করে।
    Google Sheets rate-limit/temporary error হলে ১-২ বার retry করে, যাতে দ্রুত পরপর ক্লিকে
    ভুল করে 'কিছুই নেই' না দেখায়। কয়েক সেকেন্ডের জন্য ফলাফল ক্যাশে রাখে যাতে একই Dashboard
    রেন্ডারের মধ্যে (যেখানে অনেক রোগীর জন্য বারবার একই শীট পড়া লাগে) API কল কম হয় এবং দ্রুত হয়।"""
    cache_key = _records_cache_key(ws)
    with _records_cache_lock:
        generation = _records_cache_generation.get(cache_key, 0)
        if _use_cache:
            entry = _records_cache.get(cache_key)
        else:
            entry = None
        if entry is not None:
            ts, cached = entry
            if time.monotonic() - ts < _RECORDS_CACHE_TTL:
                return cached
    try:
        result = [] if ws.row_count < 2 else ws.get_all_records()
        _sheet_warnings.pop((cache_key[0], ws.title), None)
        with _records_cache_lock:
            changed_during_read = (
                _records_cache_generation.get(cache_key, 0) != generation
            )
            if not changed_during_read:
                _records_cache[cache_key] = (time.monotonic(), result)
        if changed_during_read and _race_retries > 0:
            return safe_get_all_records(
                ws,
                _retries,
                _use_cache=False,
                _race_retries=_race_retries - 1,
            )
        return result
    except gspread.exceptions.APIError as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if _retries > 0 and status in (429, 500, 503):
            time.sleep(1.5)
            return safe_get_all_records(
                ws, _retries - 1, _use_cache, _race_retries
            )
        _sheet_warnings[(cache_key[0], ws.title)] = f"শীট '{ws.title}' পড়তে API এরর: {e}"
        return []
    except Exception as e:
        _sheet_warnings[(cache_key[0], ws.title)] = f"শীট '{ws.title}' পড়তে সমস্যা: {e}"
        return []


def _records_from_batch_values(values: list[list]) -> list[dict]:
    """Match gspread get_all_records semantics for values.batchGet output."""
    if not values or values == [[]] or not values[0]:
        return []
    headers = values[0]
    if len(headers) != len(set(headers)):
        raise gspread.exceptions.GSpreadException(
            "the header row in the worksheet is not unique"
        )
    width = len(headers)
    rows = []
    for source_row in values[1:]:
        row = list(source_row[:width])
        row.extend([""] * (width - len(row)))
        rows.append(numericise_all(row, False, "", False, []))
    return to_records(headers, rows)


def batch_get_records(sheet_names: list[str]) -> dict[str, list[dict]]:
    """Read multiple worksheets with one Sheets values.batchGet request.

    Tenant identity is asserted for every worksheet and each result uses the
    same tenant-scoped cache as safe_get_all_records().
    """
    names = list(dict.fromkeys(str(name) for name in sheet_names if name))
    if not names:
        return {}

    worksheets = {name: _worksheet(name) for name in names}
    result: dict[str, list[dict]] = {}
    missing: list[str] = []
    generations: dict[str, int] = {}
    now = time.monotonic()
    for name, ws in worksheets.items():
        key = _records_cache_key(ws)
        with _records_cache_lock:
            entry = _records_cache.get(key)
            generations[name] = _records_cache_generation.get(key, 0)
        if entry is not None and now - entry[0] < _RECORDS_CACHE_TTL:
            result[name] = entry[1]
        else:
            missing.append(name)

    if missing:
        ranges = [f"'{name.replace(chr(39), chr(39) * 2)}'" for name in missing]
        response = _get_spreadsheet().values_batch_get(
            ranges,
            params={"valueRenderOption": "FORMATTED_VALUE"},
        )
        value_ranges = response.get("valueRanges", [])
        for index, name in enumerate(missing):
            values = value_ranges[index].get("values", []) if index < len(value_ranges) else []
            records = _records_from_batch_values(values)
            ws = worksheets[name]
            key = _records_cache_key(ws)
            with _records_cache_lock:
                changed_during_read = (
                    _records_cache_generation.get(key, 0)
                    != generations[name]
                )
                if not changed_during_read:
                    _records_cache[key] = (time.monotonic(), records)
            if changed_during_read:
                records = safe_get_all_records(ws, _use_cache=False)
            _sheet_warnings.pop((key[0], ws.title), None)
            result[name] = records

    return {name: result.get(name, []) for name in names}


_sheet_warnings: dict = {}


def get_sheet_warning(sheet_name: str) -> str:
    """সংশ্লিষ্ট শীটে সবশেষ কোনো read-warning (যেমন duplicate header) থাকলে সেটা রিটার্ন করে ও মুছে দেয়।
    bot.py-এর কোনো ফাংশন এটা ইউজারকে দেখাতে চাইলে reply-তে জুড়ে দিতে পারে।"""
    return _sheet_warnings.pop((_active_sheet_id(), sheet_name), "")


def _invalidate_cache(ws) -> None:
    """কোনো শীটে write (append/update) হওয়ার পর সেই শীটের cache মুছে দেয়, যাতে সাথে সাথে
    করা পরবর্তী read পুরনো (stale) ডেটা না দেখায়।"""
    with _records_cache_lock:
        key = _records_cache_key(ws)
        _records_cache.pop(key, None)
        _records_cache_generation[key] = _records_cache_generation.get(key, 0) + 1


from google.oauth2.service_account import Credentials
from datetime import datetime

from config import bd_now
from data_contract import apply_to_headers, encounter_id_from_treatment, metadata, new_record_id

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class _SyncTokenBucket:
    def __init__(self, per_minute: int, burst: int):
        self.rate = max(1, per_minute) / 60.0
        self.capacity = max(1, min(burst, per_minute))
        self.tokens = float(self.capacity)
        self.updated = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(
                    self.capacity,
                    self.tokens + (now - self.updated) * self.rate,
                )
                self.updated = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                delay = (1 - self.tokens) / self.rate
            time.sleep(delay)


_read_rate = _SyncTokenBucket(
    int(os.getenv("SHEETS_READ_REQUESTS_PER_MINUTE", "240")),
    int(os.getenv("SHEETS_READ_BURST", "20")),
)
_write_rate = _SyncTokenBucket(
    int(os.getenv("SHEETS_WRITE_REQUESTS_PER_MINUTE", "45")),
    int(os.getenv("SHEETS_WRITE_BURST", "5")),
)


class RateLimitedHTTPClient(HTTPClient):
    """Rate-limit actual HTTP requests, rather than high-level business calls."""

    def request(self, method, endpoint, **kwargs):
        is_read = str(method).upper() in {"GET", "HEAD", "OPTIONS"}
        bucket = _read_rate if is_read else _write_rate
        for attempt in range(4):
            bucket.acquire()
            try:
                return super().request(method, endpoint, **kwargs)
            except gspread.exceptions.APIError as error:
                status = getattr(getattr(error, "response", None), "status_code", None)
                retryable = status == 429 or (is_read and status in {500, 503})
                if not retryable or attempt == 3:
                    raise
                time.sleep(min(8.0, (2 ** attempt) + random.random()))
        raise RuntimeError("unreachable")

_clients_by_thread = {}
_spreadsheet_cache = {}
_worksheet_cache = {}
_cache_lock = threading.RLock()


def _get_client():
    thread_id = threading.get_ident()
    with _cache_lock:
        if thread_id not in _clients_by_thread:
            creds = Credentials.from_service_account_file(
                config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
            )
            _clients_by_thread[thread_id] = gspread.authorize(
                creds, http_client=RateLimitedHTTPClient
            )
        return _clients_by_thread[thread_id]


def _get_spreadsheet():
    sheet_id = _active_sheet_id()
    thread_id = threading.get_ident()
    key = (thread_id, sheet_id)
    with _cache_lock:
        if key not in _spreadsheet_cache:
            spreadsheet = _get_client().open_by_key(sheet_id)
            if str(spreadsheet.id) != str(sheet_id):
                raise RuntimeError("Opened spreadsheet does not match resolved tenant")
            _spreadsheet_cache[key] = spreadsheet
        return _spreadsheet_cache[key]


def _worksheet(name: str):
    sheet_id = _active_sheet_id()
    key = (threading.get_ident(), sheet_id, name)
    with _cache_lock:
        if key not in _worksheet_cache:
            ws = _get_spreadsheet().worksheet(name)
            _assert_current_worksheet(ws)
            _worksheet_cache[key] = ws
        return _worksheet_cache[key]


def _append_unified_row(
    ws,
    row: list,
    record_type: str,
    record_id: str = "",
    *,
    encounter_id: str = "",
    provider_id: str = "",
    source_type: str = "human_entry",
    ai_generated: bool = False,
    human_verified: bool = True,
    value_input_option: str = "RAW",
    extra_values: dict[str, object] | None = None,
) -> None:
    """Append a legacy-compatible row plus Unified Data Architecture metadata."""
    headers = ws.row_values(1)
    active_clinic_id = (
        "RELIFE-DENTAL"
        if config.DENTAL_GOOGLE_SHEET_ID
        and str(_active_sheet_id()) == str(config.DENTAL_GOOGLE_SHEET_ID)
        else "RELIFE-PHYSIO"
    )
    envelope = metadata(
        record_type,
        legacy_record_id=record_id,
        clinic_id=active_clinic_id,
        encounter_id=encounter_id,
        provider_id=provider_id,
        source_type=source_type,
        ai_generated=ai_generated,
        human_verified=human_verified,
    )
    output_row = apply_to_headers(headers, row, envelope) if headers else list(row)
    for header, value in (extra_values or {}).items():
        if header in headers:
            output_row[headers.index(header)] = value
    ws.append_row(output_row, value_input_option=value_input_option)
    _invalidate_cache(ws)


def _batch_update_cells(ws, row_number: int, updates: dict[int, object]) -> None:
    """Update non-contiguous cells in one atomic Sheets values batch request."""
    if not updates:
        return
    data = [
        {"range": rowcol_to_a1(row_number, column), "values": [[value]]}
        for column, value in sorted(updates.items())
    ]
    ws.batch_update(data, value_input_option="USER_ENTERED")
    _invalidate_cache(ws)


def _inventory_department(value: object) -> str:
    department = department_access.normalize_department(value)
    if department in {
        department_access.Department.PHYSIO,
        department_access.Department.DENTAL,
    }:
        return department.value
    return ""


def _find_inventory_row(item_name: str, department: str):
    """Find an item only inside one explicit department."""
    target_department = _inventory_department(department)
    if not target_department:
        return None, None, None
    ws = _worksheet(config.SHEET_INVENTORY)
    values = ws.get_all_values()
    if not values:
        return None, None, None
    header = values[0]
    if "Item_Name" not in header or "Department" not in header:
        return None, header, ws
    name_idx = header.index("Item_Name")
    department_idx = header.index("Department")
    target = item_name.strip().casefold()
    for row_number, row in enumerate(values[1:], start=2):
        row_name = row[name_idx].strip().casefold() if len(row) > name_idx else ""
        row_department = (
            _inventory_department(row[department_idx])
            if len(row) > department_idx else ""
        )
        if row_name == target and row_department == target_department:
            return row_number, header, ws
    return None, header, ws


def get_all_inventory(departments=None) -> list:
    """Return inventory inside explicit scope; missing Department fails closed."""
    rows = safe_get_all_records(_worksheet(config.SHEET_INVENTORY))
    return filter_records_by_departments(rows, departments)


def adjust_inventory_stock(
    item_name: str,
    change: float,
    reason: str,
    staff: str,
    department: str,
) -> dict:
    """Adjust one item inside one department and persist a scoped audit log."""
    target_department = _inventory_department(department)
    if not target_department:
        return {"ok": False, "error": "সঠিক Department পাওয়া যায়নি"}
    try:
        row_num, header, ws = _find_inventory_row(item_name, target_department)
        if row_num is None:
            return {
                "ok": False,
                "error": (
                    f"'{item_name}' নামে item {target_department} inventory-তে "
                    "পাওয়া যায়নি"
                ),
            }
        stock_idx = header.index("Current_Stock") + 1
        id_idx = header.index("Item_ID") + 1 if "Item_ID" in header else None
        lastupd_idx = header.index("Last_Updated") + 1 if "Last_Updated" in header else None
        minimum_header = "Minimum_Stock" if "Minimum_Stock" in header else "Minimum"
        minimum_idx = header.index(minimum_header) + 1 if minimum_header in header else None

        current = _safe_float(ws.cell(row_num, stock_idx).value)
        new_balance = max(0, current + change)
        now = bd_now()
        updates = {stock_idx: new_balance}
        if lastupd_idx:
            updates[lastupd_idx] = now.strftime("%Y-%m-%d %I:%M %p")
        _batch_update_cells(ws, row_num, updates)
        item_id = ws.cell(row_num, id_idx).value if id_idx else ""

        try:
            log_ws = _worksheet(config.SHEET_INVENTORY_LOG)
            _append_unified_row(
                log_ws,
                [
                    now.strftime("%Y-%m-%d %I:%M %p"),
                    item_id,
                    item_name,
                    change,
                    reason,
                    staff,
                    new_balance,
                ],
                "inventory_log",
                new_record_id("inventory_log"),
                provider_id=staff,
                extra_values={"Department": target_department},
            )
        except Exception as error:
            print(f"⚠️ Inventory log লিখতে সমস্যা হয়েছে: {error}")

        low_stock = False
        if minimum_idx:
            minimum = _safe_float(ws.cell(row_num, minimum_idx).value)
            low_stock = minimum > 0 and new_balance <= minimum
        return {
            "ok": True,
            "new_balance": new_balance,
            "item_id": item_id,
            "department": target_department,
            "low_stock": low_stock,
        }
    except Exception as error:
        return {"ok": False, "error": str(error)}


def get_active_therapist_names() -> list[str]:
    ws = _worksheet(config.SHEET_STAFF)
    records = safe_get_all_records(ws)
    names = []
    for row in records:
        role = str(row.get("Role", "")).strip().lower()
        status = str(row.get("Status", "")).strip().lower()
        name = str(row.get("Full_Name", "")).strip()
        if role == "therapist" and status == "active" and name and name not in names:
            names.append(name)
    return names


def get_staff_by_telegram_id(telegram_id: int) -> dict | None:
    # 08_Staff on the Physio workbook is the common staff registry.
    with sheet_scope.use_sheet(config.GOOGLE_SHEET_ID):
        ws = _worksheet(config.SHEET_STAFF)
        records = safe_get_all_records(ws)
    for row in records:
        if str(row.get("Telegram_ID", "")).strip() == str(telegram_id):
            if str(row.get("Status", "")).strip().lower() == "inactive":
                return None
            return row
    return None


def get_staff_department_access(staff_id: str | None = None) -> list[dict]:
    """Build authorization assignments only from 08_Staff.

    The function name is retained so existing callers remain stable, but the
    deleted Staff_Department_Access worksheet is never opened. Role and
    Primary_Department on the active 08_Staff row are the single source of
    truth. Invalid or blank values fail closed.
    """
    with sheet_scope.use_sheet(config.GOOGLE_SHEET_ID):
        records = safe_get_all_records(_worksheet(config.SHEET_STAFF))
    target = str(staff_id or "").strip()
    assignments = []
    for row in records:
        row_staff_id = str(row.get("Staff_ID", "")).strip()
        if not row_staff_id or (target and row_staff_id != target):
            continue
        if str(row.get("Status", "")).strip().casefold() != "active":
            continue
        department = department_access.normalize_department(
            row.get("Primary_Department")
        )
        role = department_access.normalize_role(row.get("Role"))
        if department is None or role is None:
            continue
        if (
            department is department_access.Department.ALL
            and role is not department_access.Role.OWNER
        ):
            continue
        assignments.append({
            "Staff_ID": row_staff_id,
            "Department": department.value,
            "Role": role.value,
            "Status": "Active",
        })
    return assignments


def filter_patients_for_staff(
    patients: list[dict], staff: dict, mappings: list[dict]
) -> list[dict]:
    """Apply the central department decision to patient records when enabled."""
    if not config.DEPARTMENT_ENFORCEMENT_ENABLED:
        return patients
    return [
        patient for patient in patients
        if authorize_record(
            staff, patient, AccessAction.READ, mappings
        ).allowed
    ]


def _patient_id_prefix() -> str:
    """Patient namespace follows the active department workbook."""
    if (
        config.DENTAL_GOOGLE_SHEET_ID
        and str(_active_sheet_id()) == str(config.DENTAL_GOOGLE_SHEET_ID)
    ):
        return "DT"
    return "PT"


def _next_patient_id(ws) -> str:
    prefix = _patient_id_prefix()
    ids = ws.col_values(1)[1:]
    numbers = []
    for value in ids:
        value = str(value or "").strip().upper()
        if value.startswith(prefix):
            try:
                numbers.append(int(value[len(prefix):]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"{prefix}{next_num:04d}"


def add_patient(data: dict, created_by: str) -> str:
    ws = _worksheet(config.SHEET_PATIENTS)
    patient_id = _next_patient_id(ws)
    now = bd_now()

    row = [
        patient_id,
        now.strftime("%Y-%m-%d"),
        now.strftime("%I:%M %p"),
        data.get("Full_Name", ""),
        data.get("Father_Husband_Name", ""),
        data.get("Phone", ""),
        data.get("Alternative_Phone", ""),
        data.get("Date_of_Birth", ""),
        data.get("Age", ""),
        data.get("Gender", ""),
        data.get("Blood_Group", ""),
        data.get("Occupation", ""),
        data.get("Address", ""),
        data.get("Department", ""),
        data.get("Diagnosis", ""),
        data.get("Therapist", ""),
        "",
        "",
        "",
        "Due",
        data.get("Total_Bill", 0),
        0,
        data.get("Total_Bill", 0),
        data.get("Referral", ""),
        data.get("Remarks", ""),
        "Active",
        created_by,
        now.strftime("%Y-%m-%d %I:%M %p"),
        now.strftime("%Y-%m-%d %I:%M %p"),
    ]
    _append_unified_row(ws, row, "patient", patient_id, provider_id=created_by)
    new_row_number = len(ws.get_all_values())
    phone_val = data.get("Phone", "")
    alt_phone_val = data.get("Alternative_Phone", "")
    phone_updates = {}
    if phone_val:
        phone_updates[6] = "'" + str(phone_val)
    if alt_phone_val:
        phone_updates[7] = "'" + str(alt_phone_val)
    _batch_update_cells(ws, new_row_number, phone_updates)
    return patient_id


def get_all_patients() -> list[dict]:
    ws = _worksheet(config.SHEET_PATIENTS)
    records = safe_get_all_records(ws)

    for r in records:
        phone = str(r.get("Phone", "")).strip()
        if phone.isdigit() and len(phone) == 10:
            r["Phone"] = "0" + phone

        alt = str(r.get("Alternative_Phone", "")).strip()
        if alt.isdigit() and len(alt) == 10:
            r["Alternative_Phone"] = "0" + alt

    return records


def get_recent_patients(limit: int = 8) -> list[dict]:
    """সবচেয়ে নতুন রেজিস্ট্রেশন করা রোগীরা আগে (Patient ID অনুযায়ী নতুন থেকে পুরনো)।
    সার্চ/টাইপ না করে সরাসরি বাটনে বেছে নেওয়ার জন্য ব্যবহৃত হয়।"""
    all_patients = get_all_patients()
    return list(reversed(all_patients))[:limit]


def get_patients_for_therapist(therapist_name: str) -> list[dict]:
    all_patients = get_all_patients()
    return [
        p for p in all_patients
        if p.get("Therapist", "").strip() == therapist_name.strip()
        and p.get("Status", "").strip() == "Active"
    ]


def search_patients(query: str) -> list[dict]:
    query = query.strip().lower()
    all_patients = get_all_patients()
    return [
        p for p in all_patients
        if query in str(p.get("Full_Name", "")).lower()
        or query in str(p.get("Phone", ""))
        or query in str(p.get("Patient_ID", "")).lower()
    ]


def search_patients_for_staff(
    query: str, staff: dict, mappings: list[dict]
) -> list[dict]:
    return filter_patients_for_staff(search_patients(query), staff, mappings)


def find_patient_by_phone(phone: str) -> dict | None:
    """একই ফোন নম্বরে আগে থেকে Active রোগী আছে কিনা চেক করে।"""
    phone = phone.strip()
    for p in get_all_patients():
        if (
            str(p.get("Phone", "")).strip() == phone
            and str(p.get("Status", "")).strip() == "Active"
        ):
            return p
    return None


def _next_appointment_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("AP"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"AP{next_num:04d}"


def add_appointment(data: dict, created_by: str) -> str:
    ws = _worksheet(config.SHEET_APPOINTMENTS)
    appointment_id = _next_appointment_id(ws)
    row = [
        appointment_id,
        data.get("Date", ""),
        data.get("Time", ""),
        data.get("Patient_ID", ""),
        data.get("Patient_Name", ""),
        data.get("Department", ""),
        data.get("Therapist", ""),
        "Scheduled",
        data.get("Remarks", ""),
    ]
    _append_unified_row(
        ws, row, "appointment", appointment_id,
        provider_id=created_by,
    )
    return appointment_id


def get_all_appointments() -> list[dict]:
    ws = _worksheet(config.SHEET_APPOINTMENTS)
    return safe_get_all_records(ws)


def get_appointments_for_date(date_str: str) -> list[dict]:
    all_appts = get_all_appointments()
    return [a for a in all_appts if str(a.get("Date", "")).strip() == date_str.strip()]


def get_appointments_for_date_for_staff(
    date_str: str, staff: dict, mappings: list[dict]
) -> list[dict]:
    """Return only appointments readable through current explicit assignments."""
    return [
        appointment
        for appointment in get_appointments_for_date(date_str)
        if authorize_record(
            staff, appointment, AccessAction.READ, mappings
        ).allowed
    ]


def get_appointments_for_therapist(therapist_name: str) -> list[dict]:
    all_appts = get_all_appointments()
    return [
        a for a in all_appts
        if a.get("Therapist", "").strip() == therapist_name.strip()
        and a.get("Status", "").strip() == "Scheduled"
    ]


def _next_attendance_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("AT"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"AT{next_num:04d}"


def get_today_attendance(staff_id: str, date_str: str) -> dict | None:
    ws = _worksheet(config.SHEET_ATTENDANCE)
    records = safe_get_all_records(ws)
    for idx, row in enumerate(records, start=2):
        if (
            str(row.get("Staff_ID", "")).strip() == str(staff_id).strip()
            and str(row.get("Date", "")).strip() == date_str
        ):
            row["_row_number"] = idx
            return row
    return None


def _update_attendance_cell(row_number: int, col_index: int, value):
    ws = _worksheet(config.SHEET_ATTENDANCE)
    ws.update_cell(row_number, col_index, value)
    _invalidate_cache(ws)


def attendance_check_in(staff: dict, location_note: str = "") -> str:
    now = bd_now()
    date_str = now.strftime("%Y-%m-%d")
    staff_id = staff.get("Staff_ID", "") or str(staff.get("Telegram_ID", ""))

    existing = get_today_attendance(staff_id, date_str)
    if existing:
        return str(existing.get("Check_In", "")).strip() or "আগেই Check In করা হয়েছে"

    ws = _worksheet(config.SHEET_ATTENDANCE)
    time_str = now.strftime("%I:%M %p")
    attendance_id = _next_attendance_id(ws)

    shift_start = now.replace(hour=8, minute=45, second=0, microsecond=0)
    late_min = max(0, int((now - shift_start).total_seconds() // 60))
    status = "Late" if late_min > 15 else "Present"

    row = [
        attendance_id,
        date_str,
        staff_id,
        staff.get("Full_Name", ""),
        staff.get("Role", ""),
        time_str,
        "", "", "",
        "",
        late_min,
        "",
        status,
        location_note,
    ]
    _append_unified_row(
        ws, row, "attendance", attendance_id,
        provider_id=staff_id,
    )
    return time_str


def attendance_break_out(staff_id: str, date_str: str) -> str | None:
    record = get_today_attendance(staff_id, date_str)
    if not record:
        return None
    time_str = bd_now().strftime("%I:%M %p")
    _update_attendance_cell(record["_row_number"], 7, time_str)
    return time_str


def attendance_break_in(staff_id: str, date_str: str) -> str | None:
    record = get_today_attendance(staff_id, date_str)
    if not record:
        return None
    time_str = bd_now().strftime("%I:%M %p")
    _update_attendance_cell(record["_row_number"], 8, time_str)
    return time_str


def attendance_check_out(staff_id: str, date_str: str) -> dict | None:
    record = get_today_attendance(staff_id, date_str)
    if not record:
        return None
    ws = _worksheet(config.SHEET_ATTENDANCE)
    now = bd_now()
    time_str = now.strftime("%I:%M %p")

    try:
        check_in = datetime.strptime(f"{date_str} {record.get('Check_In','')}", "%Y-%m-%d %I:%M %p")
        check_in = check_in.replace(tzinfo=now.tzinfo)
    except ValueError:
        check_in = now

    total_minutes = (now - check_in).total_seconds() / 60

    break_out = record.get("Break_Out", "")
    break_in = record.get("Break_In", "")
    if break_out and break_in:
        try:
            bo = datetime.strptime(f"{date_str} {break_out}", "%Y-%m-%d %I:%M %p")
            bi = datetime.strptime(f"{date_str} {break_in}", "%Y-%m-%d %I:%M %p")
            total_minutes -= (bi - bo).total_seconds() / 60
        except ValueError:
            pass

    working_hours = round(total_minutes / 60, 2)

    shift_end = now.replace(hour=19, minute=45, second=0, microsecond=0)
    raw_overtime_min = max(0, (now - shift_end).total_seconds() / 60)

    late_cell = ws.cell(record["_row_number"], 11).value
    try:
        late_min = float(late_cell) if late_cell not in (None, "") else 0
    except (TypeError, ValueError):
        late_min = 0

    overtime_min = max(0, raw_overtime_min - late_min)
    overtime = round(overtime_min / 60, 2)

    _batch_update_cells(
        ws,
        record["_row_number"],
        {9: time_str, 10: working_hours, 12: overtime},
    )

    return {"time": time_str, "working_hours": working_hours, "overtime": overtime}


def get_patient_by_id(patient_id: str) -> dict | None:
    """একটা নির্দিষ্ট Patient_ID দিয়ে রোগীর সম্পূর্ণ তথ্য বের করে।"""
    patient_id = patient_id.strip()
    for p in get_all_patients():
        if str(p.get("Patient_ID", "")).strip() == patient_id:
            return p
    return None


def get_patient_by_id_for_staff(
    patient_id: str, staff: dict, mappings: list[dict]
) -> dict | None:
    patient = get_patient_by_id(patient_id)
    if patient is None:
        return None
    visible = filter_patients_for_staff([patient], staff, mappings)
    return visible[0] if visible else None


def update_patient_payment(patient_id: str, additional_paid: float, discount: float = 0) -> dict | None:
    """
    রোগীর 02_Patients শীটে Payment_Status / Total_Bill / Paid_Amount / Due_Amount
    কলামগুলো (কলাম ২০-২৩) আপডেট করে। রিটার্ন করে নতুন বিল স্ট্যাটাস।
    """
    ws = _worksheet(config.SHEET_PATIENTS)
    cell = ws.find(patient_id.strip())
    if cell is None:
        return None
    row_number = cell.row
    row_values = ws.row_values(row_number)

    def _num(idx):
        try:
            return float(row_values[idx] or 0)
        except (IndexError, ValueError):
            return 0.0

    total_bill = _num(20)   # কলাম ২১: Total_Bill
    paid_amount = _num(21)  # কলাম ২২: Paid_Amount

    new_paid = paid_amount + additional_paid
    new_due = max(0.0, total_bill - new_paid - discount)
    status = "Paid" if new_due <= 0 else "Due"

    _batch_update_cells(
        ws,
        row_number,
        {
            20: status,
            22: new_paid,
            23: new_due,
            29: bd_now().strftime("%Y-%m-%d %I:%M %p"),
        },
    )

    return {
        "total_bill": total_bill,
        "paid_amount": new_paid,
        "due_amount": new_due,
        "status": status,
    }


def update_appointment_status(appointment_id: str, status: str) -> bool:
    ws = _worksheet(config.SHEET_APPOINTMENTS)
    cell = ws.find(appointment_id)
    if cell is None:
        return False
    ws.update_cell(cell.row, 8, status)
    _invalidate_cache(ws)
    return True


def set_appointment_received_by(appointment_id: str, staff_name: str) -> bool:
    """Received_By কলাম থাকলে কে রোগী receive করল সেটা লেখে।

    কলামটা না থাকলে চুপচাপ False — Stage 0 কোনো schema বদলায় না, আর
    এই তথ্য না লেখা গেলেও double-receive guard status দিয়েই কাজ করে।
    """
    ws = _worksheet(config.SHEET_APPOINTMENTS)
    headers = ws.row_values(1)
    if "Received_By" not in headers:
        return False
    cell = ws.find(str(appointment_id).strip(), in_column=1)
    if cell is None:
        return False
    ws.update_cell(cell.row, headers.index("Received_By") + 1, staff_name)
    _invalidate_cache(ws)
    return True


def get_appointment_by_id(appointment_id: str) -> dict | None:
    """Appointment_ID দিয়ে একটা নির্দিষ্ট অ্যাপয়েন্টমেন্ট খুঁজে বের করে।"""
    for a in get_all_appointments():
        if str(a.get("Appointment_ID", "")).strip() == str(appointment_id).strip():
            return a
    return None


def get_appointment_by_id_for_staff(
    appointment_id: str,
    staff: dict,
    mappings: list[dict],
    action: AccessAction = AccessAction.READ,
) -> dict | None:
    """Resolve the target record and authorize its Department; fail closed."""
    appointment = get_appointment_by_id(appointment_id)
    if appointment is None:
        return None
    decision = authorize_record(staff, appointment, action, mappings)
    return appointment if decision.allowed else None


def update_appointment_status_for_staff(
    appointment_id: str,
    status: str,
    staff: dict,
    mappings: list[dict],
) -> bool:
    """Authorize immediately before the final appointment status write."""
    if get_appointment_by_id_for_staff(
        appointment_id, staff, mappings, AccessAction.WRITE
    ) is None:
        return False
    return update_appointment_status(appointment_id, status)


def has_payment_for_appointment(appointment_id: str, date_str: str) -> bool:
    """এই অ্যাপয়েন্টমেন্টের জন্য আগে থেকে রেজিস্টার এন্ট্রি (Payment) তৈরি হয়েছে কিনা চেক করে (একই অ্যাপয়েন্টমেন্টে দুইবার এন্ট্রি ঠেকাতে)।"""
    tag = f"APT:{appointment_id}"
    for p in get_all_payments():
        if str(p.get("Date", "")).strip() == str(date_str).strip() and tag in str(p.get("Remarks", "")):
            return True
    return False


# ===== Payment & Package Functions =====

def _next_package_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    nums = [int(i.replace("PKG", "")) for i in ids if i.startswith("PKG")]
    n = max(nums) + 1 if nums else 1
    return f"PKG{n:04d}"


def _next_receipt_no(ws) -> str:
    ids = ws.col_values(1)[1:]
    nums = [int(i.replace("RC", "")) for i in ids if i.startswith("RC")]
    n = max(nums) + 1 if nums else 1
    return f"RC{n:04d}"


def add_package(patient_id: str, patient_name: str, total_sessions: int, package_amount: float, paid_amount: float) -> str:
    ws = _worksheet(config.SHEET_PACKAGES)
    package_id = _next_package_id(ws)
    due_amount = package_amount - paid_amount
    status = "Active"
    row = [
        package_id, patient_id, patient_name, total_sessions, 0, total_sessions,
        package_amount, paid_amount, due_amount,
        bd_now().strftime("%Y-%m-%d"), status,
    ]
    _set_department_by_header(ws, row, _patient_department(patient_id))
    _append_unified_row(ws, row, "package", package_id)
    return package_id


def get_active_package_for_patient(patient_id: str) -> dict | None:
    package_sheet_name = getattr(config, "SHEET_PACKAGES", None)
    if not package_sheet_name:
        return None
    try:
        ws = _worksheet(package_sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return None
    records = safe_get_all_records(ws)
    for idx, r in enumerate(records, start=2):
        if str(r.get("Patient_ID", "")).strip() == patient_id.strip() and r.get("Status", "") == "Active":
            r["_row_number"] = idx
            return r
    return None


def update_package_payment(row_number: int, additional_paid: float) -> bool:
    ws = _worksheet(config.SHEET_PACKAGES)
    row = ws.row_values(row_number)
    paid_amount = float(row[7] or 0) + additional_paid
    package_amount = float(row[6] or 0)
    due_amount = package_amount - paid_amount
    _batch_update_cells(ws, row_number, {8: paid_amount, 9: due_amount})
    return True


def increment_package_session(patient_id: str, count: int = 1) -> bool:
    pkg = get_active_package_for_patient(patient_id)
    if pkg is None:
        return False
    ws = _worksheet(config.SHEET_PACKAGES)
    used = int(pkg.get("Sessions_Used", 0)) + max(0, int(count or 0))
    total = int(pkg.get("Total_Sessions", 0))
    remaining = max(0, total - used)
    row_number = pkg["_row_number"]
    updates = {5: used, 6: remaining}
    if remaining == 0:
        updates[11] = "Completed"
    _batch_update_cells(ws, row_number, updates)
    return True


def decrement_package_session(patient_id: str, count: int = 1) -> bool:
    """increment_package_session-এর উল্টো — ভুল সেশন এন্ট্রি ডিলিট হলে সেশন কাউন্ট ফিরিয়ে আনার
    জন্য ব্যবহার হয় (delete_payment থেকে কল হয়)। রোগীর সবচেয়ে সাম্প্রতিক প্যাকেজ রো ধরা হয় —
    এটা Active অথবা সদ্য Completed যেকোনোটাই হতে পারে (উদাহরণ: শেষ সেশন এন্ট্রিটাই ডিলিট হচ্ছে
    যেটার ফলে প্যাকেজ Completed হয়ে গিয়েছিল)। সেশন কমিয়ে দরকার হলে আবার Active করে দেয়।"""
    ws = _worksheet(config.SHEET_PACKAGES)
    records = safe_get_all_records(ws, _use_cache=False)
    row_number = None
    pkg = None
    for idx, r in enumerate(records, start=2):
        if str(r.get("Patient_ID", "")).strip() == patient_id.strip():
            row_number = idx
            pkg = r  # সবচেয়ে নিচের (সর্বশেষ) মিলটাই থেকে যাবে
    if pkg is None:
        return False
    used = max(
        0,
        int(pkg.get("Sessions_Used", 0) or 0) - max(0, int(count or 0)),
    )
    total = int(pkg.get("Total_Sessions", 0) or 0)
    remaining = max(0, total - used)
    updates = {5: used, 6: remaining}
    if remaining > 0 and str(pkg.get("Status", "")).strip() == "Completed":
        updates[11] = "Active"
    _batch_update_cells(ws, row_number, updates)
    return True


def _next_daily_sl(ws, date_str: str) -> int:
    """সেই তারিখে এখন পর্যন্ত কতগুলো পেমেন্ট এন্ট্রি হয়েছে তা গুনে পরের SL নম্বর দেয়।"""
    try:
        records = safe_get_all_records(ws)
    except Exception:
        return 1
    count = sum(1 for r in records if str(r.get("Date", "")) == date_str)
    return count + 1


def add_payment(data: dict) -> str:
    ws = _worksheet(config.SHEET_PAYMENTS)
    receipt_no = _next_receipt_no(ws)
    date_str = bd_now().strftime("%Y-%m-%d")
    sl = _next_daily_sl(ws, date_str)
    row = [
        receipt_no,
        date_str,
        sl,
        data.get("Patient_ID", ""),
        data.get("Patient_Name", ""),
        data.get("Department", ""),
        data.get("Amount", 0),
        data.get("Discount", 0),
        data.get("Due", 0),
        data.get("Payment_Method", ""),
        data.get("Received_By", ""),
        data.get("Remarks", ""),
    ]
    _append_unified_row(
        ws, row, "payment", receipt_no,
        provider_id=str(data.get("Received_By", "")),
    )
    return receipt_no


def record_payment_transaction(
    patient_id: str,
    amount: float,
    sessions: int,
    data: dict,
    *,
    idempotency_key: str,
) -> tuple[dict | None, str]:
    """Apply a payment flow under one caller-held tenant write lock.

    The request marker prevents a Telegram update retry from appending a second
    receipt. The async adapter serializes this whole function per clinic.
    """
    marker = f"REQ:{idempotency_key}"
    ws = _worksheet(config.SHEET_PAYMENTS)
    for row in safe_get_all_records(ws, _use_cache=False):
        if marker in str(row.get("Remarks", "")):
            return None, str(row.get("Receipt_No", "") or row.get("Receipt_ID", ""))

    bill_status = None
    if amount > 0:
        bill_status = update_patient_payment(patient_id, amount, discount=0)

    payload = dict(data)
    remarks = str(payload.get("Remarks", "")).strip()
    payload["Remarks"] = f"{remarks} | {marker}".strip(" |")
    if bill_status:
        payload["Due"] = bill_status["due_amount"]
    receipt_no = add_payment(payload)

    if int(sessions or 0) > 0:
        increment_package_session(patient_id, int(sessions))
    return bill_status, receipt_no


def get_today_payments_by_staff(staff_name: str) -> list[dict]:
    """আজকের তারিখে নির্দিষ্ট স্টাফের করা পেমেন্ট/সেশন এন্ট্রিগুলো লিস্ট করে (Delete ফিচারের
    জন্য)। শুধু নিজের করা এন্ট্রি এবং শুধু আজকের এন্ট্রি — এর বাইরে কিছু রিটার্ন করে না।
    সর্বশেষ এন্ট্রি সবার আগে থাকে।"""
    ws = _worksheet(config.SHEET_PAYMENTS)
    records = safe_get_all_records(ws, _use_cache=False)
    today_str = bd_now().strftime("%Y-%m-%d")
    result = []
    for idx, r in enumerate(records, start=2):
        if str(r.get("Date", "")).strip() != today_str:
            continue
        if str(r.get("Received_By", "")).strip() != str(staff_name).strip():
            continue
        r["_row_number"] = idx
        result.append(r)
    result.sort(key=lambda r: r["_row_number"], reverse=True)
    return result


def delete_payment(receipt_no: str, deleted_by: str) -> dict | None:
    """একটা পেমেন্ট/সেশন এন্ট্রি মুছে দেয় এবং এর প্রভাব রিভার্স করে:
    - রোগীর Paid_Amount/Due_Amount/Status ফিরিয়ে আনে (টাকা নেওয়া থাকলে)
    - প্যাকেজের Sessions_Used কমিয়ে দেয় (সেশন এন্ট্রি থাকলে)
    - Delete_Log শীটে মোছার আগের সম্পূর্ণ ডেটা সংরক্ষণ করে (কে, কখন, কী মুছল)
    এন্ট্রি খুঁজে না পেলে None রিটার্ন করে, নাহলে মোছা এন্ট্রির ডেটা (dict) রিটার্ন করে।

    সতর্কতা: এই ফাংশন ধরে নেয় যে এন্ট্রিটা আজকেরই এবং এর পরে ওই রোগীর হিসেবে অন্য কোনো
    পরিবর্তন হয়নি (তাই শুধু আজকের এন্ট্রি ডিলিট করা যায় — get_today_payments_by_staff দিয়ে
    সীমাবদ্ধ রাখা হয়েছে)।"""
    ws = _worksheet(config.SHEET_PAYMENTS)
    try:
        cell = ws.find(str(receipt_no).strip(), in_column=1)
    except gspread.exceptions.CellNotFound:
        cell = None
    if cell is None:
        return None
    row_number = cell.row
    row_values = ws.row_values(row_number)

    def _val(idx):
        try:
            return row_values[idx]
        except IndexError:
            return ""

    entry = {
        "Receipt_No": _val(0), "Date": _val(1), "SL": _val(2),
        "Patient_ID": _val(3), "Patient_Name": _val(4), "Department": _val(5),
        "Amount": _val(6), "Discount": _val(7), "Due": _val(8),
        "Payment_Method": _val(9), "Received_By": _val(10), "Remarks": _val(11),
    }

    amount = _safe_float(entry["Amount"])
    discount = _safe_float(entry["Discount"])
    patient_id = str(entry["Patient_ID"]).strip()

    sessions = 0
    m = re.search(r"Sessions:\s*(\d+)", entry["Remarks"] or "")
    if m:
        sessions = int(m.group(1))

    # ১) Payments শীট থেকে রো মোছা
    ws.delete_rows(row_number)
    _invalidate_cache(ws)

    # ২) রোগীর Paid/Due হিসাব রিভার্স করা (টাকা নেওয়া থাকলে)
    if amount > 0 and patient_id:
        try:
            update_patient_payment(patient_id, -amount, discount=-discount)
        except Exception as e:
            print(f"⚠️ রোগীর Paid/Due রিভার্স করতে সমস্যা হয়েছে: {e}")

    # ৩) প্যাকেজের সেশন কমানো (সেশন এন্ট্রি থাকলে)
    if sessions > 0 and patient_id:
        try:
            decrement_package_session(patient_id, sessions)
        except Exception as e:
            print(f"⚠️ প্যাকেজ সেশন রিভার্স করতে সমস্যা হয়েছে: {e}")

    # ৪) Delete_Log শীটে রেকর্ড রাখা
    try:
        log_ws = _worksheet(getattr(config, "SHEET_DELETE_LOG", "Delete_Log"))
        _append_unified_row(
            log_ws,
            [
                bd_now().strftime("%Y-%m-%d %I:%M %p"),
                deleted_by,
                "Payment/Session",
                entry["Receipt_No"],
                entry["Patient_ID"],
                entry["Patient_Name"],
                entry["Amount"],
                sessions,
                json.dumps(entry, ensure_ascii=False),
            ],
            "delete_log",
            new_record_id("delete_log"),
            provider_id=deleted_by,
        )
    except Exception as e:
        print(f"⚠️ Delete_Log-এ লেখা ব্যর্থ হয়েছে (এন্ট্রি তবুও মোছা হয়েছে): {e}")

    return entry


def get_all_payments() -> list[dict]:
    ws = _worksheet(config.SHEET_PAYMENTS)
    return safe_get_all_records(ws)


def _department_scope_values(departments) -> frozenset[str]:
    """Normalize an explicit report scope; an empty/unknown scope grants nothing."""
    values = set()
    for value in departments or ():
        normalized = department_access.normalize_department(value)
        if normalized is department_access.Department.ALL:
            values.update({
                department_access.Department.PHYSIO.value,
                department_access.Department.DENTAL.value,
            })
        elif normalized in {
            department_access.Department.PHYSIO,
            department_access.Department.DENTAL,
        }:
            values.add(normalized.value)
    return frozenset(values)


def filter_records_by_departments(
    records: list[dict], departments
) -> list[dict]:
    """Fail closed: rows missing a recognized Department never enter reports."""
    scope = _department_scope_values(departments)
    if not scope:
        return []
    return [
        row for row in records
        if (
            (normalized := department_access.normalize_department(
                row.get("Department")
            )) is not None
            and normalized.value in scope
        )
    ]


def get_scoped_report_records(departments) -> dict[str, list[dict]]:
    """Read and scope report inputs before returning them to presentation code."""
    data = batch_get_records([config.SHEET_PATIENTS, config.SHEET_PAYMENTS])
    return {
        config.SHEET_PATIENTS: filter_records_by_departments(
            data.get(config.SHEET_PATIENTS, []), departments
        ),
        config.SHEET_PAYMENTS: filter_records_by_departments(
            data.get(config.SHEET_PAYMENTS, []), departments
        ),
    }


def get_payments_for_patient(patient_id: str) -> list[dict]:
    all_payments = get_all_payments()
    return [p for p in all_payments if str(p.get("Patient_ID", "")).strip() == str(patient_id).strip()]


def get_appointments_for_patient(patient_id: str) -> list[dict]:
    all_apts = get_all_appointments()
    return [a for a in all_apts if str(a.get("Patient_ID", "")).strip() == str(patient_id).strip()]


def get_treatment_notes_for_patient(patient_id: str) -> list[dict]:
    ws = _worksheet(config.SHEET_TREATMENTS)
    all_notes = safe_get_all_records(ws)
    return [n for n in all_notes if str(n.get("Patient_ID", "")).strip() == str(patient_id).strip()]


# ===== Treatment Note & Next Visit Functions =====

def _next_treatment_id(ws) -> str:
    """05_Treatments শীটে পরবর্তী Treatment_ID (TRxxxx ফরম্যাটে) বের করে।"""
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("TR"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"TR{next_num:04d}"


def _normalize_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name or "").lower())


def _sheet_value_for_header(header: str, data: dict) -> str:
    if header in data:
        return data.get(header, "")

    norm = _normalize_header(header)
    remarks = data.get("Remarks", "")
    treatment_given = data.get("Treatment_Given", "")
    synonyms = {
        "treatmentid": data.get("Treatment_ID", ""),
        "date": data.get("Date", ""),
        "patientid": data.get("Patient_ID", ""),
        "patientname": data.get("Patient_Name", ""),
        "diagnosis": data.get("Diagnosis", ""),
        "subjective": data.get("SOAP_Subjective", data.get("Subjective", data.get("Diagnosis", ""))),
        "objective": data.get("SOAP_Objective", data.get("Objective", treatment_given)),
        "assessment": data.get("SOAP_Assessment", data.get("Assessment", "")),
        "plan": data.get("SOAP_Plan", data.get("Plan", "")),
        "treatmentgiven": treatment_given,
        "exercise": data.get("Exercise", ""),
        "electrotherapy": data.get("Electrotherapy", ""),
        "manualtherapy": data.get("Manual_Therapy", ""),
        "sessionno": data.get("Session_No", ""),
        "createdby": data.get("Created_By", created_by if (created_by := data.get("_created_by", "")) else data.get("Created_By", "")),
        "therapist": data.get("Created_By", data.get("Therapist", "")),
        "remarks": remarks,
        "note": data.get("Clinical_Note", remarks or treatment_given),
        "notes": data.get("Clinical_Note", remarks or treatment_given),
        "machines": data.get("Machines", ""),
        "planid": data.get("Plan_ID", ""),
        "protocolday": data.get("Protocol_Day", data.get("Session_No", "")),
        "pain": data.get("Pain", ""),
        "rom": data.get("ROM", ""),
        "mmt": data.get("MMT", ""),
        "specialtest": data.get("Special_Test", ""),
        "electrosetting": data.get("Electro_Setting", ""),
        "homeexercise": data.get("Home_Exercise", ""),
        "voicenote": data.get("Voice_Note", ""),
        "photo": data.get("Photo", ""),
        "video": data.get("Video", ""),
    }
    return synonyms.get(norm, data.get(header, ""))


def add_treatment_note(data: dict, created_by: str) -> str:
    """
    05_Treatments শীটে নতুন ট্রিটমেন্ট নোট যোগ করে।
    শীটের হেডার অনুযায়ী ডাইনামিক্যালি row build করে যাতে নতুন clinical
    field (যেমন Machines, Pain, ROM, MMT, SOAP) থাকলেও সেগুলো সেভ হয়।
    """
    ws = _worksheet(config.SHEET_TREATMENTS)
    treatment_id = _next_treatment_id(ws)
    payload = dict(data)
    payload.setdefault("Treatment_ID", treatment_id)
    payload.setdefault("Date", bd_now().strftime("%Y-%m-%d"))
    payload.setdefault("Created_By", created_by)
    payload.setdefault("_created_by", created_by)
    envelope = metadata(
        "treatment",
        legacy_record_id=treatment_id,
        encounter_id=encounter_id_from_treatment(treatment_id),
        provider_id=created_by,
        source_type=str(payload.get("Source_Type", "human_entry") or "human_entry"),
        ai_generated=_safe_bool(payload.get("AI_Generated"), False),
        human_verified=_safe_bool(payload.get("Human_Verified"), True),
    )
    payload.update(envelope)

    headers = ws.row_values(1)
    if headers:
        row = [_sheet_value_for_header(header, payload) for header in headers]
        ws.append_row(row, value_input_option="RAW")
    else:
        row = [
            treatment_id,
            payload.get("Date", ""),
            payload.get("Patient_ID", ""),
            payload.get("Patient_Name", ""),
            payload.get("Diagnosis", ""),
            payload.get("Treatment_Given", ""),
            payload.get("Exercise", ""),
            payload.get("Electrotherapy", ""),
            payload.get("Manual_Therapy", ""),
            payload.get("Session_No", ""),
            created_by,
            payload.get("Remarks", ""),
            payload.get("Plan_ID", ""),
            payload.get("Machines", ""),
        ]
        ws.append_row(row, value_input_option="RAW")
    _invalidate_cache(ws)
    return treatment_id


def update_next_visit(patient_id: str, next_visit_date: str) -> bool:
    """02_Patients শীটে Next_Visit কলাম (কলাম ১৯) আপডেট করে।"""
    ws = _worksheet(config.SHEET_PATIENTS)
    cell = ws.find(patient_id.strip())
    if cell is None:
        return False
    ws.update_cell(cell.row, 19, next_visit_date)
    _invalidate_cache(ws)
    return True


def get_last_treatment_note_for_patient(patient_id: str) -> dict | None:
    """
    রোগীর সবচেয়ে সাম্প্রতিক ট্রিটমেন্ট নোট ফেরত দেয় (থাকলে), না থাকলে None।
    "গতকালের মতোই" রিপিট-এন্ট্রি ফিচারের জন্য ব্যবহৃত হয়।
    """
    notes = get_treatment_notes_for_patient(patient_id)
    if not notes:
        return None
    return notes[-1]


# ===== Treatment Plan Functions (মাল্টি-সেশন প্ল্যান, কোর্সের জন্য একবার লেখা হয়) =====

def _next_plan_id(ws) -> str:
    """12_Treatment_Plans শীটে পরবর্তী Plan_ID (PLxxxx ফরম্যাটে) বের করে।"""
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("PL"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"PL{next_num:04d}"


def _next_assessment_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("AS"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"AS{next_num:04d}"


def _patient_department(patient_id: str) -> str:
    """রোগীর নিজের Department রেকর্ড থেকে খুঁজে আনে; না পেলে ফাঁকা।"""
    patient = get_patient_by_id(patient_id)
    if not patient:
        return ""
    return str(patient.get("Department", "")).strip()


def _set_department_by_header(ws, row: list, department: str) -> None:
    """headers-এ Department কলাম থাকলে, সঠিক পজিশনে বসিয়ে দেয় (কলাম অর্ডার বদলালেও নিরাপদ)।"""
    headers = ws.row_values(1)
    if "Department" not in headers:
        return
    idx = headers.index("Department")
    if len(row) <= idx:
        row.extend([""] * (idx + 1 - len(row)))
    row[idx] = department


def add_assessment(patient_id: str, category: str, test_data: dict, created_by: str) -> str:
    """10_Assessments শীটে প্রাথমিক মূল্যায়নের ফলাফল সেভ করে (টেস্ট-রেছাল্ট JSON আকারে,
    কারণ প্রতিটা category-র টেস্ট আলাদা — আলাদা কলাম বানালে শীট এলোমেলো হয়ে যেত)."""
    ws = _worksheet(config.SHEET_ASSESSMENTS)
    assessment_id = _next_assessment_id(ws)
    now = bd_now()
    row = [
        assessment_id,
        patient_id,
        category,
        json.dumps(test_data, ensure_ascii=False),
        created_by,
        now.strftime("%Y-%m-%d %I:%M %p"),
    ]
    _set_department_by_header(ws, row, _patient_department(patient_id))
    _append_unified_row(
        ws, row, "assessment", assessment_id,
        provider_id=created_by,
    )
    return assessment_id


def get_assessments_for_patient(patient_id: str) -> list[dict]:
    """একজন রোগীর সব প্রাথমিক মূল্যায়ন রেকর্ড ফেরত দেয় (নতুন থেকে পুরনো), Test_Data ডিকোড করে।"""
    ws = _worksheet(config.SHEET_ASSESSMENTS)
    records = safe_get_all_records(ws)
    out = []
    for r in records:
        if str(r.get("Patient_ID", "")).strip() == patient_id.strip():
            r = dict(r)
            try:
                r["Test_Data"] = json.loads(r.get("Test_Data", "") or "{}")
            except (json.JSONDecodeError, TypeError):
                r["Test_Data"] = {}
            out.append(r)
    return list(reversed(out))


def add_treatment_plan(data: dict, created_by: str) -> str:
    """
    12_Treatment_Plans শীটে নতুন ট্রিটমেন্ট প্ল্যান যোগ করে — পুরো চিকিৎসা-কোর্সের জন্য
    একবার লেখা হয় (দৈনিক নোট নয়)। Sessions_Done সবসময় 0 দিয়ে শুরু হয়, Status="Active"।
    """
    ws = _worksheet(config.SHEET_TREATMENT_PLANS)
    plan_id = _next_plan_id(ws)
    row = [
        plan_id,
        data.get("Patient_ID", ""),
        data.get("Patient_Name", ""),
        data.get("Diagnosis", ""),
        data.get("Total_Sessions", ""),
        0,
        data.get("Exercise_Plan", ""),
        data.get("Electrotherapy_Plan", ""),
        data.get("Manual_Therapy_Plan", ""),
        created_by,
        bd_now().strftime("%Y-%m-%d"),
        "Active",
    ]
    _set_department_by_header(ws, row, _patient_department(data.get("Patient_ID", "")))
    _append_unified_row(
        ws, row, "treatment_plan", plan_id,
        provider_id=created_by,
    )
    _invalidate_cache(ws)
    return plan_id


def get_active_plan_for_patient(patient_id: str) -> dict | None:
    """রোগীর বর্তমান Active ট্রিটমেন্ট প্ল্যান ফেরত দেয় (থাকলে), না থাকলে None।"""
    ws = _worksheet(config.SHEET_TREATMENT_PLANS)
    records = safe_get_all_records(ws)
    for idx, r in enumerate(records, start=2):
        if (
            str(r.get("Patient_ID", "")).strip() == patient_id.strip()
            and str(r.get("Status", "")).strip() == "Active"
        ):
            r["_row_number"] = idx
            return r
    return None


def get_last_plan_for_patient(patient_id: str) -> dict | None:
    """
    রোগীর সবচেয়ে সাম্প্রতিক প্ল্যান ফেরত দেয় (Active/Completed যেকোনো স্ট্যাটাস), না থাকলে None।
    নতুন প্ল্যান বানানোর সময় আগের প্ল্যানের মান ডিফল্ট হিসেবে (- দিলে) ব্যবহার করতে কাজে লাগে।
    """
    ws = _worksheet(config.SHEET_TREATMENT_PLANS)
    records = safe_get_all_records(ws)
    patient_plans = [
        r for r in records
        if str(r.get("Patient_ID", "")).strip() == patient_id.strip()
    ]
    if not patient_plans:
        return None
    return patient_plans[-1]


def increment_plan_session(patient_id: str) -> bool:
    """
    রোগীর Active প্ল্যানের Sessions_Done ১ বাড়ায়। Total_Sessions-এ পৌঁছালে
    Status="Completed" করে দেয় (increment_package_session-এর প্যাটার্ন অনুসরণ করে)।
    """
    plan = get_active_plan_for_patient(patient_id)
    if plan is None:
        return False
    ws = _worksheet(config.SHEET_TREATMENT_PLANS)
    done = int(plan.get("Sessions_Done", 0) or 0) + 1
    total = int(plan.get("Total_Sessions", 0) or 0)
    row_number = plan["_row_number"]
    updates = {6: done}
    if total and done >= total:
        updates[12] = "Completed"
    _batch_update_cells(ws, row_number, updates)
    return True


def get_daily_register(date_str: str | None = None, departments=None) -> dict:
    """
    ০৬_Payments শীট থেকে আজকের সব এন্ট্রি নিয়ে Sl/Patient/Session/Bill/Paid/Due/Status
    সহ রেজিস্টার বানায়, দিনশেষের টোটাল হিসাব করে।
    """
    if date_str is None:
        date_str = bd_now().strftime("%Y-%m-%d")
    payments_today = [
        p for p in filter_records_by_departments(get_all_payments(), departments)
        if str(p.get("Date", "")).strip() == date_str
    ]
    rows = []
    total_bill = total_paid = total_due = total_sessions = 0.0
    for p in payments_today:
        remarks = str(p.get("Remarks", ""))
        sessions = 1
        if remarks.startswith("Sessions:"):
            try:
                sessions = int(remarks.split(":", 1)[1].strip())
            except ValueError:
                sessions = 1
        paid = float(p.get("Amount", 0) or 0)
        due = float(p.get("Due", 0) or 0)
        bill = paid + due
        if due <= 0:
            status = "✅ Paid"
        elif paid > 0:
            status = "🟡 আংশিক বাকি"
        else:
            status = "🔴 বাকি"
        rows.append({
            "Sl": p.get("SL", ""),
            "Patient_Name": p.get("Patient_Name", ""),
            "Sessions": sessions,
            "Bill": bill,
            "Paid": paid,
            "Due": due,
            "Status": status,
        })
        total_bill += bill
        total_paid += paid
        total_due += due
        total_sessions += sessions
    return {
        "date": date_str,
        "rows": rows,
        "total_patients": len(rows),
        "total_sessions": int(total_sessions),
        "total_bill": total_bill,
        "total_paid": total_paid,
        "total_due": total_due,
    }


def _next_report_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("RP"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"RP{next_num:04d}"


def add_report(data: dict, uploaded_by: str) -> str:
    ws = _worksheet(config.SHEET_REPORTS)
    report_id = _next_report_id(ws)
    row = [
        report_id,
        data.get("Patient_ID", ""),
        data.get("Patient_Name", ""),
        data.get("File_Telegram_ID", ""),
        data.get("File_Name", ""),
        data.get("File_Type", ""),
        bd_now().strftime("%Y-%m-%d %I:%M %p"),
        uploaded_by,
        data.get("File_Drive_Link", ""),
    ]
    _set_department_by_header(ws, row, _patient_department(data.get("Patient_ID", "")))
    _append_unified_row(
        ws, row, "report", report_id,
        provider_id=uploaded_by,
    )
    return report_id


def get_reports_for_patient(patient_id: str) -> list[dict]:
    ws = _worksheet(config.SHEET_REPORTS)
    all_reports = safe_get_all_records(ws)
    return [r for r in all_reports if str(r.get("Patient_ID", "")).strip() == str(patient_id).strip()]


def get_report_by_id(report_id: str) -> dict | None:
    """একটা নির্দিষ্ট Report_ID দিয়ে রিপোর্টের মেটাডেটা বের করে।"""
    ws = _worksheet(config.SHEET_REPORTS)
    all_reports = safe_get_all_records(ws)
    for r in all_reports:
        if str(r.get("Report_ID", "")).strip() == str(report_id).strip():
            return r
    return None


def get_daily_report(date_str: str) -> dict:
    patients = safe_get_all_records(_worksheet(config.SHEET_PATIENTS))
    payments = safe_get_all_records(_worksheet(config.SHEET_PAYMENTS))

    patient_count = sum(1 for p in patients if str(p.get("Registration_Date", "")).strip() == date_str)
    day_payments = [p for p in payments if str(p.get("Date", "")).strip() == date_str]
    total_income = sum(float(p.get("Amount", 0) or 0) for p in day_payments)
    unique_today = set(str(p.get("Patient_ID", "")).strip() for p in day_payments if str(p.get("Patient_ID", "")).strip())

    return {
        "patient_count": patient_count,
        "payment_count": len(day_payments),
        "total_income": total_income,
        "total_patients_today": len(unique_today),
    }


def get_month_running_total(year: int, month: int, up_to_day: int) -> dict:
    patients = safe_get_all_records(_worksheet(config.SHEET_PATIENTS))
    payments = safe_get_all_records(_worksheet(config.SHEET_PAYMENTS))
    month_prefix = f"{year:04d}-{month:02d}-"

    patient_count = 0
    for p in patients:
        d = str(p.get("Registration_Date", "")).strip()
        if d.startswith(month_prefix):
            try:
                if int(d.split("-")[2]) <= up_to_day:
                    patient_count += 1
            except (IndexError, ValueError):
                continue

    payment_count, total_income = 0, 0.0
    unique_month = set()
    for p in payments:
        d = str(p.get("Date", "")).strip()
        if d.startswith(month_prefix):
            try:
                if int(d.split("-")[2]) <= up_to_day:
                    payment_count += 1
                    total_income += float(p.get("Amount", 0) or 0)
                    pid = str(p.get("Patient_ID", "")).strip()
                    if pid:
                        unique_month.add(pid)
            except (IndexError, ValueError):
                continue

    return {
        "patient_count": patient_count,
        "payment_count": payment_count,
        "total_income": total_income,
        "total_patients_month": len(unique_month),
    }


def get_daily_patient_list(date_str: str, departments=None) -> list[dict]:
    payments = _finance_scoped_records(
        safe_get_all_records(_worksheet(config.SHEET_PAYMENTS)), departments
    )
    day_payments = [p for p in payments if str(p.get("Date", "")).strip() == date_str]
    day_payments.sort(key=lambda p: str(p.get("SL", "")))
    return [
        {
            "name": p.get("Patient_Name", ""),
            "session": p.get("Session_Type", ""),
            "amount": float(p.get("Amount", 0) or 0),
        }
        for p in day_payments
    ]



# ===== Case Study (AI Lesson) Functions =====

def _next_case_study_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("CS"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"CS{next_num:04d}"


def add_case_study_lesson(session_id: str, patient_id: str, patient_name: str,
                           lesson_number: int, lesson_title: str, content: str,
                           created_by: str) -> str:
    """15_Case_Studies শীটে একটা Lesson সেভ করে। এক Session_ID-এর সব Lesson একসাথে
    থাকে যাতে ভিন্ন রোগীর কেস আলাদা থাকে, গোলানো না যায়।"""
    ws = _worksheet(config.SHEET_CASE_STUDIES)
    case_study_id = _next_case_study_id(ws)
    row = [
        case_study_id,
        session_id,
        patient_id,
        patient_name,
        lesson_number,
        lesson_title,
        content,
        created_by,
        bd_now().strftime("%Y-%m-%d %I:%M %p"),
    ]
    _append_unified_row(
        ws, row, "case_study", case_study_id,
        provider_id=created_by,
        source_type="human_or_ai_lesson",
        human_verified=False,
    )
    return case_study_id


def get_case_study_sessions_for_patient(patient_id: str) -> list[dict]:
    """একজন রোগীর সব সেভ করা কেস-স্টাডি সেশন লিস্ট করে (Session_ID অনুযায়ী গ্রুপ করা)।"""
    ws = _worksheet(config.SHEET_CASE_STUDIES)
    all_rows = safe_get_all_records(ws)
    sessions = {}
    for r in all_rows:
        if str(r.get("Patient_ID", "")).strip() != str(patient_id).strip():
            continue
        sid = r.get("Session_ID", "")
        if sid not in sessions:
            sessions[sid] = {
                "Session_ID": sid,
                "Patient_ID": patient_id,
                "Patient_Name": r.get("Patient_Name", ""),
                "Timestamp": r.get("Timestamp", ""),
                "Lesson_Count": 0,
            }
        sessions[sid]["Lesson_Count"] += 1
    return list(sessions.values())


def get_case_study_lessons(session_id: str) -> list[dict]:
    """একটা নির্দিষ্ট Session_ID-এর সব Lesson ফেরত দেয় (Lesson_Number অনুযায়ী সাজানো)।"""
    ws = _worksheet(config.SHEET_CASE_STUDIES)
    all_rows = safe_get_all_records(ws)
    lessons = [r for r in all_rows if str(r.get("Session_ID", "")).strip() == str(session_id).strip()]
    lessons.sort(key=lambda r: int(r.get("Lesson_Number", 0) or 0))
    return lessons


def get_all_staff() -> list[dict]:
    """সব সক্রিয় (Status != Inactive) স্টাফের রেকর্ড রিটার্ন করে।"""
    ws = _worksheet(config.SHEET_STAFF)
    records = safe_get_all_records(ws)
    return [r for r in records if str(r.get("Status", "")).strip().lower() != "inactive"]


def get_staff_needing_break_reminder(date_str: str) -> list[dict]:
    """যাদের আজ Check-In আছে কিন্তু এখনো Break Out নেই এবং Check-Out ও নেই — এমন স্টাফের
    রেকর্ড রিটার্ন করে (দুপুর ১টার বিরতি reminder job-এর জন্য)।"""
    ws = _worksheet(config.SHEET_ATTENDANCE)
    records = safe_get_all_records(ws)
    today_by_staff = {}
    for row in records:
        if str(row.get("Date", "")).strip() == date_str:
            today_by_staff[str(row.get("Staff_ID", "")).strip()] = row

    pending = []
    for staff in get_all_staff():
        staff_id = str(staff.get("Staff_ID", "")).strip()
        att = today_by_staff.get(staff_id)
        if not att:
            continue
        if att.get("Check_In") and not att.get("Break_Out") and not att.get("Check_Out"):
            pending.append(staff)
    return pending


def get_salary_summary(staff_id: str, month: str) -> dict:
    """একজন স্টাফের নির্দিষ্ট মাসের বেতন সারাংশ রিটার্ন করে (Monthly Salary, Paid, Due)।
    month ফরম্যাট: 'YYYY-MM'"""
    staff_ws = _worksheet(config.SHEET_STAFF)
    staff_records = safe_get_all_records(staff_ws)
    staff = next(
        (r for r in staff_records if str(r.get("Staff_ID", "")).strip() == str(staff_id).strip()),
        None,
    )
    if not staff:
        return {}
    try:
        monthly_salary = _safe_float(staff.get("Salary", 0))
    except (TypeError, ValueError):
        monthly_salary = 0

    ws = _worksheet(config.SHEET_SALARY)
    records = safe_get_all_records(ws)
    paid = sum(
        _safe_float(r.get("Amount", 0))
        for r in records
        if str(r.get("Staff_ID", "")).strip() == str(staff_id).strip()
        and str(r.get("Month", "")).strip() == month
    )
    return {
        "Staff_ID": staff_id,
        "Full_Name": staff.get("Full_Name", ""),
        "Telegram_ID": staff.get("Telegram_ID", ""),
        "Monthly_Salary": monthly_salary,
        "Paid": paid,
        "Due": round(monthly_salary - paid, 2),
    }


def get_payments_made_by(paid_by_name: str, limit: int = 30) -> list[dict]:
    """একজন Owner নিজে যতগুলো বেতন কিস্তি দিয়েছে, তার পুরো লিস্ট রিটার্ন করে (নতুন থেকে পুরনো)।
    প্রতিটা রেকর্ডে সংশ্লিষ্ট স্টাফের Full_Name ও যোগ করে দেয়।"""
    ws = _worksheet(config.SHEET_SALARY)
    records = safe_get_all_records(ws)
    rows = [
        r for r in records
        if str(r.get("Paid_By", "")).strip() == str(paid_by_name).strip()
    ]
    rows.sort(key=lambda r: str(r.get("Timestamp", "")), reverse=True)
    rows = rows[:limit]

    staff_records = safe_get_all_records(_worksheet(config.SHEET_STAFF))
    name_by_id = {
        str(s.get("Staff_ID", "")).strip(): s.get("Full_Name", "")
        for s in staff_records
    }
    for r in rows:
        r["Staff_Full_Name"] = name_by_id.get(str(r.get("Staff_ID", "")).strip(), r.get("Staff_ID", ""))
    return rows


def get_staff_salary_history(staff_id: str, limit: int = 20) -> list[dict]:
    """একজন স্টাফের সব বেতন কিস্তির হিস্টোরি রিটার্ন করে (নতুন থেকে পুরনো)।"""
    ws = _worksheet(config.SHEET_SALARY)
    records = safe_get_all_records(ws)
    rows = [
        r for r in records
        if str(r.get("Staff_ID", "")).strip() == str(staff_id).strip()
    ]
    rows.sort(key=lambda r: str(r.get("Timestamp", "")), reverse=True)
    return rows[:limit]


def _next_salary_payment_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("SP"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"SP{next_num:04d}"


def _staff_primary_department(staff_id: str) -> str:
    """08_Staff-এর Primary_Department থেকে বেতনের বিভাগ নেয়; অস্পষ্ট হলে ফাঁকা।"""
    for record in safe_get_all_records(_worksheet(config.SHEET_STAFF)):
        if str(record.get("Staff_ID", "")).strip() != str(staff_id).strip():
            continue
        value = str(record.get("Primary_Department", "")).strip()
        return value if value in _FINANCE_DEPARTMENTS else ""
    return ""


def add_salary_payment_checked(
    staff_id: str,
    month: str,
    amount: float,
    paid_by: str,
    note: str = "",
    paid_from: str = config.CASH_CUSTODIAN_HOME_TREASURY,
) -> dict:
    """Re-read the current due immediately before appending one salary payment."""
    amount = _positive_amount(amount)
    summary = get_salary_summary(staff_id, month)
    if not summary:
        return {"ok": False, "reason": "staff_not_found"}
    due = _safe_float(summary.get("Due", 0))
    if due <= 0:
        return {"ok": False, "reason": "already_paid", "due": due}
    if amount > due:
        return {"ok": False, "reason": "amount_exceeds_due", "due": due}
    payment_id = add_salary_payment(
        staff_id, month, amount, paid_by=paid_by, note=note,
        paid_from=paid_from,
        department=_staff_primary_department(staff_id),
    )
    return {
        "ok": True,
        "payment_id": payment_id,
        "remaining_due": round(due - amount, 2),
    }


def add_salary_payment(
    staff_id: str,
    month: str,
    amount: float,
    paid_by: str,
    note: str = "",
    paid_from: str = config.CASH_CUSTODIAN_HOME_TREASURY,
    department: str = "",
) -> str:
    """13_Salary শীটে একটা কিস্তি সেভ করে, কোন ভান্ডার থেকে গেল সেটাসহ।"""
    if paid_from not in config.CASH_CUSTODIANS:
        raise ValueError(f"Invalid cash custodian: {paid_from}")
    if department and department not in _FINANCE_DEPARTMENTS:
        raise ValueError(f"Invalid finance department: {department}")
    ws = _worksheet(config.SHEET_SALARY)
    headers = ws.row_values(1)
    missing = sorted(
        {"Paid_From", "Status", "Paid_At"}.difference(headers)
    )
    if missing:
        raise RuntimeError(
            "13_Salary is missing required custody columns: " + ", ".join(missing)
        )
    payment_id = _next_salary_payment_id(ws)
    now = bd_now()
    timestamp = now.strftime("%Y-%m-%d %I:%M %p")
    row = [
        payment_id,
        now.strftime("%Y-%m-%d"),
        month,
        staff_id,
        amount,
        paid_by,
        timestamp,
        note,
    ]
    if len(row) < len(headers):
        row.extend([""] * (len(headers) - len(row)))
    custody_values = {
        "Department": department,
        "Paid_From": paid_from,
        "Status": "Paid",
        "Paid_At": timestamp,
    }
    for header, value in custody_values.items():
        if header in headers:
            row[headers.index(header)] = value
    _append_unified_row(
        ws, row, "salary_payment", payment_id,
        provider_id=paid_by,
    )
    return payment_id


EXPENSE_CATEGORIES = ["ভাড়া", "ইউটিলিটি", "সরঞ্জাম/মেডিসিন", "মেইনটেন্যান্স", "মার্কেটিং", "অন্যান্য"]


def _next_expense_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("EX"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"EX{next_num:04d}"


def _positive_amount(amount: float) -> float:
    try:
        value = float(amount)
    except (TypeError, ValueError) as error:
        raise ValueError("Amount must be positive") from error
    if value <= 0:
        raise ValueError("Amount must be positive")
    return value


def _with_expense_type(record: dict) -> dict:
    normalized = dict(record)
    normalized["Type"] = (
        str(record.get("Type", "")).strip()
        or config.EXPENSE_TYPE_UNCLASSIFIED
    )
    return normalized


EXPENSE_WORKFLOW_COLUMNS = [
    "Paid_From", "Status", "Requested_By", "Approved_By",
    "Approved_At", "Paid_By", "Paid_At",
]
EXPENSE_STATUSES = {"Pending Approval", "Approved", "Rejected", "Paid"}


def _require_expense_workflow_headers(headers: list[str]) -> None:
    required = {"Expense_ID", "Type", *EXPENSE_WORKFLOW_COLUMNS}
    missing = sorted(required.difference(headers))
    if missing:
        raise RuntimeError(
            "07_Expenses is missing required expense workflow columns: "
            + ", ".join(missing)
        )


def _normalized_expense(record: dict) -> dict:
    normalized = _with_expense_type(record)
    status = str(record.get("Status", "")).strip()
    normalized["Status"] = status or "Legacy Paid"
    normalized["Paid_From"] = str(record.get("Paid_From", "")).strip() or "Unclassified"
    return normalized


def _expense_is_paid(record: dict) -> bool:
    return str(record.get("Status", "")).strip() in ("", "Paid")


def add_expense(
    category: str,
    amount: float,
    added_by: str,
    note: str = "",
    expense_type: str = config.EXPENSE_TYPE_CLINIC,
    paid_from: str = config.CASH_CUSTODIAN_RECEPTION,
    status: str = "Paid",
    approved_by: str = "",
    paid_by: str = "",
    department: str = "",
) -> str:
    """Create a direct paid expense/withdrawal with explicit custody source."""
    if expense_type not in config.EXPENSE_TYPES:
        raise ValueError(f"Invalid expense type: {expense_type}")
    if paid_from not in config.CASH_CUSTODIANS:
        raise ValueError(f"Invalid cash custodian: {paid_from}")
    if status not in EXPENSE_STATUSES:
        raise ValueError(f"Invalid expense status: {status}")
    if department and department not in _FINANCE_DEPARTMENTS:
        raise ValueError(f"Invalid finance department: {department}")
    amount = _positive_amount(amount)
    ws = _worksheet(config.SHEET_EXPENSES)
    headers = ws.row_values(1)
    _require_expense_workflow_headers(headers)

    expense_id = _next_expense_id(ws)
    now = bd_now()
    timestamp = now.strftime("%Y-%m-%d %I:%M %p")
    row = [
        expense_id,
        now.strftime("%Y-%m-%d"),
        category,
        amount,
        added_by,
        timestamp,
        note,
    ]
    if len(row) < len(headers):
        row.extend([""] * (len(headers) - len(row)))
    values = {
        "Department": department,
        "Type": expense_type,
        "Paid_From": paid_from,
        "Status": status,
        "Requested_By": added_by,
        "Approved_By": approved_by or (added_by if status == "Paid" else ""),
        "Approved_At": timestamp if status == "Paid" else "",
        "Paid_By": paid_by or (added_by if status == "Paid" else ""),
        "Paid_At": timestamp if status == "Paid" else "",
    }
    for header, value in values.items():
        if header in headers:
            row[headers.index(header)] = value
    _append_unified_row(
        ws,
        row,
        "expense",
        expense_id,
        provider_id=added_by,
        human_verified=status == "Paid",
    )
    return expense_id


def create_expense_request(
    category: str,
    amount: float,
    requested_by: str,
    note: str = "",
    department: str = "",
) -> str:
    """Reception requests a small clinic expense before paying it."""
    return add_expense(
        category,
        amount,
        requested_by,
        note=note,
        expense_type=config.EXPENSE_TYPE_CLINIC,
        paid_from=config.CASH_CUSTODIAN_RECEPTION,
        status="Pending Approval",
        department=department,
    )


def _finance_scoped_records(records: list[dict], departments) -> list[dict]:
    """Legacy internal callers may omit scope; production bot always supplies it."""
    if departments is None:
        return records
    return filter_records_by_departments(records, departments)


def get_expense_requests(status: str, departments=None) -> list[dict]:
    if status not in EXPENSE_STATUSES:
        raise ValueError(f"Invalid expense status: {status}")
    ws = _worksheet(config.SHEET_EXPENSES)
    rows = [
        _normalized_expense(row)
        for row in _finance_scoped_records(
            safe_get_all_records(ws), departments
        )
        if str(row.get("Status", "")).strip() == status
    ]
    rows.sort(key=lambda row: str(row.get("Timestamp", "")), reverse=True)
    return rows


def _finalize_expense_status(
    expense_id: str,
    expected_status: str,
    updates: dict[str, str],
    departments=None,
) -> dict:
    ws = _worksheet(config.SHEET_EXPENSES)
    values = ws.get_all_values()
    if not values:
        return {"ok": False, "reason": "not_found"}
    headers = values[0]
    _require_expense_workflow_headers(headers)
    id_index = headers.index("Expense_ID")
    status_index = headers.index("Status")
    department_index = headers.index("Department") if "Department" in headers else -1
    allowed = None if departments is None else _department_scope_values(departments)

    for row_number, row in enumerate(values[1:], start=2):
        current_id = row[id_index].strip() if len(row) > id_index else ""
        if current_id != expense_id.strip():
            continue
        current_department = (
            _inventory_department(row[department_index])
            if department_index >= 0 and len(row) > department_index else ""
        )
        if allowed is not None and current_department not in allowed:
            return {"ok": False, "reason": "department_forbidden"}
        current_status = row[status_index].strip() if len(row) > status_index else ""
        if current_status != expected_status:
            return {
                "ok": False,
                "reason": "invalid_status",
                "status": current_status,
            }
        cell_updates = {
            headers.index(header) + 1: value
            for header, value in updates.items()
        }
        _batch_update_cells(ws, row_number, cell_updates)
        return {
            "ok": True,
            "expense_id": expense_id,
            "status": updates.get("Status", current_status),
        }
    return {"ok": False, "reason": "not_found"}


def finalize_expense_request(
    expense_id: str,
    approved_by: str,
    decision: str,
    departments=None,
) -> dict:
    """Owner approves or rejects a pending expense exactly once."""
    if decision not in {"Approved", "Rejected"}:
        raise ValueError(f"Invalid expense decision: {decision}")
    now = bd_now().strftime("%Y-%m-%d %I:%M %p")
    return _finalize_expense_status(
        expense_id,
        "Pending Approval",
        {
            "Status": decision,
            "Approved_By": approved_by,
            "Approved_At": now,
        },
        departments,
    )


def mark_expense_paid(
    expense_id: str, paid_by: str, departments=None
) -> dict:
    """Reception confirms actual payment after owner approval."""
    now = bd_now().strftime("%Y-%m-%d %I:%M %p")
    return _finalize_expense_status(
        expense_id,
        "Approved",
        {
            "Status": "Paid",
            "Paid_By": paid_by,
            "Paid_At": now,
        },
        departments,
    )




def _expense_action_for_department(
    department: str,
    function,
    *args,
    **kwargs,
):
    """Run one expense action against its explicit department workbook."""
    with sheet_scope.use_sheet(config.sheet_id_for_department(department)):
        return function(*args, **kwargs)


def finalize_expense_request_for_department(
    department: str,
    expense_id: str,
    approved_by: str,
    decision: str,
    departments=None,
) -> dict:
    return _expense_action_for_department(
        department,
        finalize_expense_request,
        expense_id,
        approved_by,
        decision,
        departments,
    )


def mark_expense_paid_for_department(
    department: str,
    expense_id: str,
    paid_by: str,
    departments=None,
) -> dict:
    return _expense_action_for_department(
        department,
        mark_expense_paid,
        expense_id,
        paid_by,
        departments,
    )


def _legacy_expense_action_across_departments(
    function,
    expense_id: str,
    *args,
    departments=None,
) -> dict:
    """Compatibility for buttons sent before department was encoded.

    Never updates when the same Expense_ID exists in more than one workbook.
    """
    allowed = _department_scope_values(departments)
    candidates = [
        department for department in _FINANCE_DEPARTMENTS
        if allowed is None or department in allowed
    ]
    matches = []
    for department in candidates:
        with sheet_scope.use_sheet(config.sheet_id_for_department(department)):
            rows = safe_get_all_records(_worksheet(config.SHEET_EXPENSES))
        if any(
            str(row.get("Expense_ID", "")).strip() == str(expense_id).strip()
            for row in rows
        ):
            matches.append(department)
    if not matches:
        return {"ok": False, "reason": "not_found"}
    if len(matches) != 1:
        return {"ok": False, "reason": "ambiguous_department"}
    return _expense_action_for_department(
        matches[0], function, expense_id, *args, departments
    )


def finalize_expense_request_legacy(
    expense_id: str, approved_by: str, decision: str, departments=None
) -> dict:
    return _legacy_expense_action_across_departments(
        finalize_expense_request,
        expense_id,
        approved_by,
        decision,
        departments=departments,
    )


def mark_expense_paid_legacy(
    expense_id: str, paid_by: str, departments=None
) -> dict:
    return _legacy_expense_action_across_departments(
        mark_expense_paid,
        expense_id,
        paid_by,
        departments=departments,
    )


def get_expenses_for_date(
    date_str: str | None = None, end_date: str | None = None, departments=None
) -> list[dict]:
    """Return expense rows in an inclusive range, defaulting to today."""
    start_date = date_str or bd_now().strftime("%Y-%m-%d")
    end_date = end_date or start_date
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    ws = _worksheet(config.SHEET_EXPENSES)
    rows = [
        _normalized_expense(row)
        for row in _finance_scoped_records(
            safe_get_all_records(ws), departments
        )
        if start_date <= str(row.get("Date", "")).strip() <= end_date
    ]
    rows.sort(key=lambda row: str(row.get("Timestamp", "")), reverse=True)
    return rows


def get_expense_total_for_month(month: str) -> float:
    """Paid clinic expenses only; household withdrawals are excluded."""
    ws = _worksheet(config.SHEET_EXPENSES)
    records = safe_get_all_records(ws)
    total = sum(
        float(row.get("Amount", 0) or 0)
        for row in records
        if str(row.get("Date", "")).strip().startswith(month)
        and str(row.get("Type", "")).strip() == config.EXPENSE_TYPE_CLINIC
        and _expense_is_paid(row)
    )
    return round(total, 2)


def _in_range(value: str, start_date: str, end_date: str) -> bool:
    text = str(value or "").strip()[:10]
    return bool(text) and start_date <= text <= end_date


def _cash_effective_date(row: dict) -> str:
    """টাকা আসলে কবে বেরিয়েছে — Paid_At, না থাকলে Date."""
    return str(row.get("Paid_At", "") or row.get("Date", "") or "").strip()[:10]


def _is_unclassified(row: dict) -> bool:
    return department_access.normalize_department(row.get("Department")) is None


def _sum_where(rows, predicate, amount_key="Amount") -> float:
    return sum(_money(row, amount_key) for row in rows if predicate(row))


def get_cash_custody_summary(
    date_str: str | None = None, end_date: str | None = None, departments=None
) -> dict:
    """Cash reconciliation over an inclusive range, defaulting to today.

    এটি নির্বাচিত সময়ের movement — opening balance এতে ধরা নেই।
    """
    start_date = date_str or bd_now().strftime("%Y-%m-%d")
    end_date = end_date or start_date
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")

    raw_payments = safe_get_all_records(_worksheet(config.SHEET_PAYMENTS))
    raw_expenses = safe_get_all_records(_worksheet(config.SHEET_EXPENSES))
    raw_movements = safe_get_all_records(_worksheet(config.SHEET_CASH_MOVEMENT))
    try:
        raw_salaries = safe_get_all_records(_worksheet(config.SHEET_SALARY))
    except Exception:  # শীট না থাকলে বাকি রিপোর্ট বন্ধ হবে না
        raw_salaries = []

    payment_rows = _finance_scoped_records(raw_payments, departments)
    expense_rows = _finance_scoped_records(raw_expenses, departments)
    movement_rows = _finance_scoped_records(raw_movements, departments)
    salary_rows = _finance_scoped_records(raw_salaries, departments)

    cash_collected = _sum_where(
        payment_rows,
        lambda row: _in_range(row.get("Date"), start_date, end_date)
        and str(row.get("Payment_Method", "")).strip().lower() == "cash",
    )

    paid_expenses = [
        row for row in expense_rows
        if _in_range(_cash_effective_date(row), start_date, end_date)
        and _expense_is_paid(row)
    ]
    paid_salaries = [
        row for row in salary_rows
        if _in_range(_cash_effective_date(row), start_date, end_date)
        and str(row.get("Status", "")).strip() in ("", "Paid")
    ]

    def _from(rows, custodian, extra=None):
        return _sum_where(
            rows,
            lambda row: str(row.get("Paid_From", "")).strip() == custodian
            and (extra is None or extra(row)),
        )

    def _type_is(expense_type):
        return lambda row: str(row.get("Type", "")).strip() == expense_type

    reception_expense = _from(paid_expenses, config.CASH_CUSTODIAN_RECEPTION)
    reception_salary = _from(paid_salaries, config.CASH_CUSTODIAN_RECEPTION)
    home_clinic_expense = _from(
        paid_expenses, config.CASH_CUSTODIAN_HOME_TREASURY,
        _type_is(config.EXPENSE_TYPE_CLINIC),
    )
    household_withdrawal = _from(
        paid_expenses, config.CASH_CUSTODIAN_HOME_TREASURY,
        _type_is(config.EXPENSE_TYPE_HOUSEHOLD),
    )
    home_salary = _from(paid_salaries, config.CASH_CUSTODIAN_HOME_TREASURY)
    bank_expense = _from(paid_expenses, config.CASH_CUSTODIAN_BANK)
    bank_salary = _from(paid_salaries, config.CASH_CUSTODIAN_BANK)

    in_range_movements = [
        row for row in movement_rows
        if _in_range(row.get("Date"), start_date, end_date)
    ]

    def _moved(rows, side, custodian):
        key = "From_Custodian" if side == "from" else "To_Custodian"
        return sum(
            _movement_amount(row) for row in rows
            if str(row.get(key, "")).strip() == custodian
        )

    accepted = [
        row for row in in_range_movements
        if str(row.get("Status", "")).strip() == "Accepted"
    ]
    pending = [
        row for row in in_range_movements
        if str(row.get("Status", "")).strip() == "Pending"
    ]

    reception_out = _moved(accepted, "from", config.CASH_CUSTODIAN_RECEPTION)
    reception_pending = _moved(pending, "from", config.CASH_CUSTODIAN_RECEPTION)
    home_in = _moved(accepted, "to", config.CASH_CUSTODIAN_HOME_TREASURY)
    home_out = _moved(accepted, "from", config.CASH_CUSTODIAN_HOME_TREASURY)
    home_pending = _moved(pending, "from", config.CASH_CUSTODIAN_HOME_TREASURY)
    bank_in = _moved(accepted, "to", config.CASH_CUSTODIAN_BANK)
    bank_out = _moved(accepted, "from", config.CASH_CUSTODIAN_BANK)

    # Department ছাড়া সারিগুলো fail-closed নিয়মে রিপোর্ট থেকে বাদ পড়ে —
    # নীরবে হারানোর বদলে আলাদা করে দেখানো হয়।
    unclassified_expense = _sum_where(
        raw_expenses,
        lambda row: _is_unclassified(row)
        and _in_range(_cash_effective_date(row), start_date, end_date)
        and _expense_is_paid(row),
    )
    unclassified_salary = _sum_where(
        raw_salaries,
        lambda row: _is_unclassified(row)
        and _in_range(_cash_effective_date(row), start_date, end_date)
        and str(row.get("Status", "")).strip() in ("", "Paid"),
    )
    unclassified_payment = _sum_where(
        raw_payments,
        lambda row: _is_unclassified(row)
        and _in_range(row.get("Date"), start_date, end_date)
        and str(row.get("Payment_Method", "")).strip().lower() == "cash",
    )
    unclassified_movement = sum(
        _movement_amount(row) for row in raw_movements
        if _is_unclassified(row)
        and _in_range(row.get("Date"), start_date, end_date)
        and str(row.get("Status", "")).strip() == "Accepted"
    )

    return {
        "Date": start_date if start_date == end_date else f"{start_date} — {end_date}",
        "Start_Date": start_date,
        "End_Date": end_date,
        "Cash_Collected": round(cash_collected, 2),
        "Reception_Expense": round(reception_expense, 2),
        "Reception_Salary": round(reception_salary, 2),
        "Reception_Handover": round(reception_out, 2),
        "Reception_In_Transit": round(reception_pending, 2),
        "Reception_Balance": round(
            cash_collected - reception_expense - reception_salary - reception_out, 2
        ),
        "Home_Received": round(home_in, 2),
        "Home_Clinic_Expense": round(home_clinic_expense, 2),
        "Home_Salary": round(home_salary, 2),
        "Household_Withdrawal": round(household_withdrawal, 2),
        "Home_Transfer_Out": round(home_out, 2),
        "Home_In_Transit": round(home_pending, 2),
        "Home_Balance": round(
            home_in - home_clinic_expense - home_salary
            - household_withdrawal - home_out,
            2,
        ),
        "Bank_Received": round(bank_in, 2),
        "Bank_Expense": round(bank_expense, 2),
        "Bank_Salary": round(bank_salary, 2),
        "Bank_Transfer_Out": round(bank_out, 2),
        "Bank_Balance": round(
            bank_in - bank_expense - bank_salary - bank_out, 2
        ),
        "Unclassified_Total": round(
            unclassified_payment + unclassified_expense
            + unclassified_salary + unclassified_movement,
            2,
        ),
    }


_RECEPTION_BALANCE_EPOCH = "2000-01-01"  # রেকর্ডের শুরুর অনেক আগে, নিরাপদ lower bound


def get_reception_cash_balance(department: str) -> float:
    """একটি বিভাগের Reception-এ এখন হাতে কত ক্যাশ আছে (all-time cumulative)।

    get_cash_custody_summary()-এর টেস্ট-করা হিসাবই পুনরায় ব্যবহার করে —
    রেকর্ডের শুরু থেকে আজ পর্যন্ত রেঞ্জ দিয়ে ডাকলে period net movement-ই
    আসলে all-time running balance হয়ে যায় (opening cash = 0 ধরে)।
    """
    today = bd_now().strftime("%Y-%m-%d")
    summary = get_cash_custody_summary(
        date_str=_RECEPTION_BALANCE_EPOCH,
        end_date=today,
        departments={department},
    )
    return summary["Reception_Balance"]


_FINANCE_DEPARTMENTS = {config.DEPARTMENT_PHYSIO, config.DEPARTMENT_DENTAL}


def _finance_department(row: dict) -> str:
    value = str(row.get("Department", "")).strip()
    return value if value in _FINANCE_DEPARTMENTS else ""


def _money(row: dict, key: str = "Amount") -> float:
    try:
        return float(row.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _movement_amount(row: dict) -> float:
    received = str(row.get("Received_Amount", "")).strip()
    return _money(row, "Received_Amount") if received else _money(row)


def _custodian(row: dict, side: str) -> str:
    raw_value = row.get("Paid_From", "") if side == "Paid" else (
        row.get(f"{side}_Custodian_ID", "")
        or row.get(f"{side}_Custodian", "")
    )
    value = str(raw_value).strip().casefold()
    if value in {"reception", "physio reception cash", "dental reception cash"}:
        return "Reception"
    if value == "home treasury":
        return "Home Treasury"
    if value in {"bank", "digital/bank", "digital"}:
        return "Digital/Bank"
    return ""


def _department_finance_summary(
    department: str,
    date_str: str,
    payment_rows: list[dict],
    expense_rows: list[dict],
    movement_rows: list[dict],
) -> dict:
    """Department-preserving owner totals; missing Department is excluded."""
    month = date_str[:7]
    payments = [row for row in payment_rows if _finance_department(row) == department]
    expenses = [row for row in expense_rows if _finance_department(row) == department]
    movements = [row for row in movement_rows if _finance_department(row) == department]

    today_collection = sum(
        _money(row) for row in payments
        if str(row.get("Date", "")).strip() == date_str
    )
    month_collection = sum(
        _money(row) for row in payments
        if str(row.get("Date", "")).strip().startswith(month)
    )
    month_clinic_expense = sum(
        _money(row) for row in expenses
        if str(row.get("Date", "")).strip().startswith(month)
        and str(row.get("Type", "")).strip() == config.EXPENSE_TYPE_CLINIC
        and _expense_is_paid(row)
    )
    month_household = sum(
        _money(row) for row in expenses
        if str(row.get("Date", "")).strip().startswith(month)
        and str(row.get("Type", "")).strip() == config.EXPENSE_TYPE_HOUSEHOLD
        and _expense_is_paid(row)
    )

    def balances(before: bool) -> dict[str, float]:
        result = {"Reception": 0.0, "Home Treasury": 0.0, "Digital/Bank": 0.0}

        def included(row: dict) -> bool:
            row_date = str(row.get("Date", "")).strip()
            return bool(row_date) and (row_date < date_str if before else row_date <= date_str)

        for row in payments:
            if not included(row):
                continue
            method = str(row.get("Payment_Method", "")).strip().casefold()
            target = "Reception" if method == "cash" else "Digital/Bank"
            result[target] += _money(row)
        for row in expenses:
            if not included(row) or not _expense_is_paid(row):
                continue
            source = _custodian(row, "Paid")
            if source:
                result[source] -= _money(row)
        for row in movements:
            if not included(row) or str(row.get("Status", "")).strip() != "Accepted":
                continue
            source = _custodian(row, "From")
            target = _custodian(row, "To")
            amount = _movement_amount(row)
            if source:
                result[source] -= amount
            if target:
                result[target] += amount
        return {key: round(value, 2) for key, value in result.items()}

    return {
        "Department": department,
        "Today_Collection": round(today_collection, 2),
        "Month_Collection": round(month_collection, 2),
        "Month_Clinic_Expense": round(month_clinic_expense, 2),
        "Month_Household_Withdrawal": round(month_household, 2),
        "Month_Net_Before_Salary": round(month_collection - month_clinic_expense, 2),
        "Opening": balances(True),
        "Closing": balances(False),
    }


def get_owner_financial_dashboard(date_str: str) -> dict:
    """Return Physio, Dental and combined business-only finance views."""
    payment_rows = safe_get_all_records(_worksheet(config.SHEET_PAYMENTS))
    expense_rows = safe_get_all_records(_worksheet(config.SHEET_EXPENSES))
    movement_rows = safe_get_all_records(_worksheet(config.SHEET_CASH_MOVEMENT))
    summaries = {
        department: _department_finance_summary(
            department, date_str, payment_rows, expense_rows, movement_rows
        )
        for department in sorted(_FINANCE_DEPARTMENTS)
    }
    combined = {
        key: round(sum(summary[key] for summary in summaries.values()), 2)
        for key in (
            "Today_Collection", "Month_Collection", "Month_Clinic_Expense",
            "Month_Household_Withdrawal", "Month_Net_Before_Salary",
        )
    }
    combined["Opening"] = {
        custodian: round(sum(s["Opening"][custodian] for s in summaries.values()), 2)
        for custodian in ("Reception", "Home Treasury", "Digital/Bank")
    }
    combined["Closing"] = {
        custodian: round(sum(s["Closing"][custodian] for s in summaries.values()), 2)
        for custodian in ("Reception", "Home Treasury", "Digital/Bank")
    }
    combined["Unclassified_Rows"] = {
        "Payments": sum(not _finance_department(row) for row in payment_rows),
        "Expenses": sum(not _finance_department(row) for row in expense_rows),
        "Cash_Movements": sum(not _finance_department(row) for row in movement_rows),
    }
    return {
        "Date": date_str,
        config.DEPARTMENT_PHYSIO: summaries[config.DEPARTMENT_PHYSIO],
        config.DEPARTMENT_DENTAL: summaries[config.DEPARTMENT_DENTAL],
        "Combined": combined,
    }


def _next_cash_movement_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for value in ids:
        if str(value).startswith("CM"):
            try:
                numbers.append(int(str(value)[2:]))
            except ValueError:
                pass
    return f"CM{((max(numbers) + 1) if numbers else 1):04d}"


def add_cash_movement(
    from_custodian: str,
    to_custodian: str,
    amount: float,
    moved_by: str,
    note: str = "",
    department: str = "",
) -> str:
    """Create a pending custody handover. This is never an expense entry."""
    if from_custodian not in config.CASH_CUSTODIANS:
        raise ValueError(f"Invalid cash custodian: {from_custodian}")
    if to_custodian not in config.CASH_CUSTODIANS:
        raise ValueError(f"Invalid cash custodian: {to_custodian}")
    if from_custodian == to_custodian:
        raise ValueError("From and To custodians must be different")
    if department and department not in _FINANCE_DEPARTMENTS:
        raise ValueError(f"Invalid finance department: {department}")
    amount = _positive_amount(amount)

    ws = _worksheet(config.SHEET_CASH_MOVEMENT)
    headers = ws.row_values(1)
    required = {"Status", "Confirmed_By", "Confirmed_At"}
    missing = sorted(required.difference(headers))
    if missing:
        raise RuntimeError(
            "21_Cash_Movement is missing required handover columns: "
            + ", ".join(missing)
        )

    movement_id = _next_cash_movement_id(ws)
    now = bd_now()
    row = [
        movement_id,
        now.strftime("%Y-%m-%d"),
        from_custodian,
        to_custodian,
        amount,
        moved_by,
        note,
        now.strftime("%Y-%m-%d %I:%M %p"),
    ]
    if len(row) < len(headers):
        row.extend([""] * (len(headers) - len(row)))
    row[headers.index("Status")] = "Pending"
    extra_values = {
        "Department": department,
        "From_Custodian_ID": (
            f"{department} Reception Cash"
            if department and from_custodian == config.CASH_CUSTODIAN_RECEPTION
            else from_custodian
        ),
        "To_Custodian_ID": to_custodian,
        "Requested_Amount": amount,
    }
    for header, value in extra_values.items():
        if header in headers:
            row[headers.index(header)] = value
    _append_unified_row(
        ws,
        row,
        "cash_movement",
        movement_id,
        provider_id=moved_by,
        human_verified=False,
    )
    return movement_id


def get_cash_movements_for_date(date_str: str, departments=None) -> list[dict]:
    """Return one tenant's cash movements for YYYY-MM-DD, newest first."""
    ws = _worksheet(config.SHEET_CASH_MOVEMENT)
    records = _finance_scoped_records(
        safe_get_all_records(ws), departments
    )
    rows = [
        row for row in records
        if str(row.get("Date", "")).strip() == date_str.strip()
    ]
    rows.sort(key=lambda row: str(row.get("Timestamp", "")), reverse=True)
    return rows


def get_pending_cash_movements(departments=None) -> list[dict]:
    """Return pending handovers for the bound clinic, newest first."""
    ws = _worksheet(config.SHEET_CASH_MOVEMENT)
    rows = [
        row for row in _finance_scoped_records(
            safe_get_all_records(ws), departments
        )
        if str(row.get("Status", "")).strip() == "Pending"
    ]
    rows.sort(key=lambda row: str(row.get("Timestamp", "")), reverse=True)
    return rows


def finalize_cash_movement(
    movement_id: str,
    confirmed_by: str,
    decision: str = "Accepted",
    departments=None,
) -> dict:
    """Accept or reject one pending handover exactly once."""
    if decision not in {"Accepted", "Rejected"}:
        raise ValueError(f"Invalid cash movement decision: {decision}")

    ws = _worksheet(config.SHEET_CASH_MOVEMENT)
    values = ws.get_all_values()
    if not values:
        return {"ok": False, "reason": "not_found"}

    headers = values[0]
    required = {"Movement_ID", "Status", "Confirmed_By", "Confirmed_At"}
    missing = sorted(required.difference(headers))
    if missing:
        raise RuntimeError(
            "21_Cash_Movement is missing required handover columns: "
            + ", ".join(missing)
        )

    id_index = headers.index("Movement_ID")
    status_index = headers.index("Status")
    department_index = headers.index("Department") if "Department" in headers else -1
    allowed = None if departments is None else _department_scope_values(departments)
    for row_number, row in enumerate(values[1:], start=2):
        current_id = row[id_index].strip() if len(row) > id_index else ""
        if current_id != movement_id.strip():
            continue
        current_department = (
            _inventory_department(row[department_index])
            if department_index >= 0 and len(row) > department_index else ""
        )
        if allowed is not None and current_department not in allowed:
            return {"ok": False, "reason": "department_forbidden"}
        current_status = row[status_index].strip() if len(row) > status_index else ""
        if current_status != "Pending":
            return {
                "ok": False,
                "reason": "already_finalized",
                "status": current_status,
            }
        confirmed_at = bd_now().strftime("%Y-%m-%d %I:%M %p")
        _batch_update_cells(
            ws,
            row_number,
            {
                status_index + 1: decision,
                headers.index("Confirmed_By") + 1: confirmed_by,
                headers.index("Confirmed_At") + 1: confirmed_at,
            },
        )
        return {
            "ok": True,
            "movement_id": movement_id,
            "status": decision,
            "confirmed_at": confirmed_at,
        }

    return {"ok": False, "reason": "not_found"}

def add_learning_event(staff_id: str, full_name: str, role: str, event_type: str,
                        item_id: str, category: str, selected: str = "", correct: str = "") -> None:
    """18_Learning_Progress শীটে quiz/tip দেখানো বা উত্তর দেওয়ার একটা লগ-এন্ট্রি যোগ করে।
    event_type: "Quiz" অথবা "Tip"।"""
    ws = _worksheet(config.SHEET_LEARNING_PROGRESS)
    now = bd_now()
    row = [
        staff_id,
        full_name,
        role,
        now.strftime("%Y-%m-%d"),
        event_type,
        item_id,
        category,
        selected,
        correct,
        now.strftime("%Y-%m-%d %I:%M %p"),
    ]
    _append_unified_row(
        ws, row, "learning_event", item_id,
        provider_id=staff_id,
    )
    _invalidate_cache(ws)


def get_learning_events_for_staff(staff_id: str) -> list[dict]:
    """একজন স্টাফের সব quiz/tip ইতিহাস রিটার্ন করে।"""
    ws = _worksheet(config.SHEET_LEARNING_PROGRESS)
    records = safe_get_all_records(ws)
    return [r for r in records if str(r.get("Staff_ID", "")).strip() == str(staff_id).strip()]


# ===== Unified consent + audit ledgers (UDA v1) =====

def record_patient_consent(
    patient_id: str,
    purpose: str,
    status: str,
    consent_version: str,
    recorded_by: str,
    notes: str = "",
) -> str:
    """Record an explicit consent decision; never infer consent from treatment data."""
    ws = _worksheet(config.SHEET_CONSENT)
    consent_id = new_record_id("CONSENT")
    now = bd_now().strftime("%Y-%m-%d %I:%M %p")
    withdrawn_at = now if str(status).strip().lower() == "withdrawn" else ""
    row = [
        consent_id,
        patient_id,
        purpose,
        status,
        consent_version,
        recorded_by,
        now,
        withdrawn_at,
        notes,
    ]
    _append_unified_row(
        ws, row, "consent", consent_id,
        provider_id=recorded_by,
    )
    return consent_id


def get_patient_consents(patient_id: str) -> list[dict]:
    ws = _worksheet(config.SHEET_CONSENT)
    return [
        row for row in safe_get_all_records(ws)
        if str(row.get("Patient_ID", "")).strip() == str(patient_id).strip()
    ]


def add_data_audit_event(
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    patient_id: str = "",
    before_value: str = "",
    after_value: str = "",
    reason: str = "",
) -> str:
    """Append an audit event without changing the target business record."""
    ws = _worksheet(config.SHEET_DATA_AUDIT)
    audit_id = new_record_id("AUDIT")
    row = [
        audit_id,
        bd_now().strftime("%Y-%m-%d %I:%M %p"),
        actor_id,
        action,
        entity_type,
        entity_id,
        patient_id,
        before_value,
        after_value,
        reason,
    ]
    _append_unified_row(
        ws, row, "audit", audit_id,
        provider_id=actor_id,
    )
    return audit_id
