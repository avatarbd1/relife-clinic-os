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
from tenant_runtime import current_tenant
from gspread.http_client import HTTPClient


def _safe_float(value):
    """শীট থেকে আসা মান (খালি স্ট্রিং, কমাযুক্ত সংখ্যা, N/A ইত্যাদি) নিরাপদে float-এ কনভার্ট করে।
    ব্যর্থ হলে 0.0 রিটার্ন করে, কখনো crash করে না।"""
    if value is None:
        return 0.0
    try:
        cleaned = str(value).replace(",", "").strip()
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
_RECORDS_CACHE_TTL = 2.0  # সেকেন্ড — একই ড্যাশবোর্ড রেন্ডারের মধ্যে বারবার একই শীট না পড়ার জন্য


def _active_sheet_id() -> str:
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


def safe_get_all_records(ws, _retries: int = 2, _use_cache: bool = True):
    """get_all_records()-এর নিরাপদ ভার্সন — sheet-এ শুধু header বা কোনো row না থাকলে crash না করে খালি list রিটার্ন করে।
    Google Sheets rate-limit/temporary error হলে ১-২ বার retry করে, যাতে দ্রুত পরপর ক্লিকে
    ভুল করে 'কিছুই নেই' না দেখায়। কয়েক সেকেন্ডের জন্য ফলাফল ক্যাশে রাখে যাতে একই Dashboard
    রেন্ডারের মধ্যে (যেখানে অনেক রোগীর জন্য বারবার একই শীট পড়া লাগে) API কল কম হয় এবং দ্রুত হয়।"""
    cache_key = _records_cache_key(ws)
    if _use_cache and cache_key in _records_cache:
        ts, cached = _records_cache[cache_key]
        if time.time() - ts < _RECORDS_CACHE_TTL:
            return cached
    try:
        if ws.row_count < 2:
            result = []
        else:
            first_row = ws.row_values(1)
            if not first_row:
                result = []
            else:
                dupes = {h for h in first_row if h and first_row.count(h) > 1}
                if dupes:
                    _sheet_warnings[(cache_key[0], ws.title)] = (
                        f"শীট '{ws.title}'-এ ডুপ্লিকেট হেডার কলাম আছে: {', '.join(dupes)} — "
                        f"ডেটা ভুল/খালি দেখাতে পারে। হেডার রো ঠিক করো।"
                    )
                else:
                    _sheet_warnings.pop((cache_key[0], ws.title), None)
                result = ws.get_all_records()
        _records_cache[cache_key] = (time.time(), result)
        return result
    except gspread.exceptions.APIError as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if _retries > 0 and status in (429, 500, 503):
            time.sleep(1.5)
            return safe_get_all_records(ws, _retries - 1, _use_cache)
        _sheet_warnings[(cache_key[0], ws.title)] = f"শীট '{ws.title}' পড়তে API এরর: {e}"
        return []
    except Exception as e:
        _sheet_warnings[(cache_key[0], ws.title)] = f"শীট '{ws.title}' পড়তে সমস্যা: {e}"
        return []


_sheet_warnings: dict = {}


def get_sheet_warning(sheet_name: str) -> str:
    """সংশ্লিষ্ট শীটে সবশেষ কোনো read-warning (যেমন duplicate header) থাকলে সেটা রিটার্ন করে ও মুছে দেয়।
    bot.py-এর কোনো ফাংশন এটা ইউজারকে দেখাতে চাইলে reply-তে জুড়ে দিতে পারে।"""
    return _sheet_warnings.pop((_active_sheet_id(), sheet_name), "")


def _invalidate_cache(ws) -> None:
    """কোনো শীটে write (append/update) হওয়ার পর সেই শীটের cache মুছে দেয়, যাতে সাথে সাথে
    করা পরবর্তী read পুরনো (stale) ডেটা না দেখায়।"""
    _records_cache.pop(_records_cache_key(ws), None)


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
) -> None:
    """Append a legacy-compatible row plus Unified Data Architecture metadata."""
    headers = ws.row_values(1)
    envelope = metadata(
        record_type,
        legacy_record_id=record_id,
        encounter_id=encounter_id,
        provider_id=provider_id,
        source_type=source_type,
        ai_generated=ai_generated,
        human_verified=human_verified,
    )
    ws.append_row(
        apply_to_headers(headers, row, envelope) if headers else row,
        value_input_option=value_input_option,
    )
    _invalidate_cache(ws)


def _find_inventory_row(item_name: str):
    ws = _worksheet(config.SHEET_INVENTORY)
    values = ws.get_all_values()
    if not values:
        return None, None, None
    header = values[0]
    if "Item_Name" not in header:
        return None, header, ws
    name_idx = header.index("Item_Name")
    target = item_name.strip().lower()
    for i, row in enumerate(values[1:], start=2):
        if len(row) > name_idx and row[name_idx].strip().lower() == target:
            return i, header, ws
    return None, header, ws


def get_all_inventory() -> list:
    ws = _worksheet(config.SHEET_INVENTORY)
    return safe_get_all_records(ws)


def adjust_inventory_stock(item_name: str, change: float, reason: str, staff: str) -> dict:
    """09_Inventory-এ item_name খুঁজে Current_Stock-এ change যোগ/বিয়োগ করে (change ঋণাত্মক
    হলে কমবে), 17_Inventory_Log-এ একটা লগ এন্ট্রি রাখে। item না পাওয়া গেলে বা কোনো সমস্যা
    হলে {"ok": False, "error": ...} রিটার্ন করে — কখনো exception raise করে caller-কে থামায়
    না, কারণ inventory ট্র্যাকিং ব্যর্থ হলেও মূল ট্রিটমেন্ট/রেজিস্ট্রেশন ফ্লো থেমে যাওয়া উচিত না।"""
    try:
        row_num, header, ws = _find_inventory_row(item_name)
        if row_num is None:
            return {"ok": False, "error": f"'{item_name}' নামে item 09_Inventory-এ পাওয়া যায়নি"}
        stock_idx = header.index("Current_Stock") + 1
        id_idx = header.index("Item_ID") + 1 if "Item_ID" in header else None
        lastupd_idx = header.index("Last_Updated") + 1 if "Last_Updated" in header else None
        minimum_idx = header.index("Minimum") + 1 if "Minimum" in header else None

        current = _safe_float(ws.cell(row_num, stock_idx).value)
        new_balance = current + change
        if new_balance < 0:
            new_balance = 0
        ws.update_cell(row_num, stock_idx, new_balance)
        now = bd_now()
        if lastupd_idx:
            ws.update_cell(row_num, lastupd_idx, now.strftime("%Y-%m-%d %I:%M %p"))
        item_id = ws.cell(row_num, id_idx).value if id_idx else ""

        try:
            log_ws = _worksheet(config.SHEET_INVENTORY_LOG)
            _append_unified_row(
                log_ws,
                [now.strftime("%Y-%m-%d %I:%M %p"), item_id, item_name, change, reason, staff, new_balance],
                "inventory_log",
                new_record_id("inventory_log"),
                provider_id=staff,
            )
        except Exception as e:
            print(f"⚠️ Inventory log লিখতে সমস্যা হয়েছে: {e}")

        low_stock = False
        if minimum_idx:
            min_val = _safe_float(ws.cell(row_num, minimum_idx).value)
            low_stock = min_val > 0 and new_balance <= min_val

        return {"ok": True, "new_balance": new_balance, "item_id": item_id, "low_stock": low_stock}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
    ws = _worksheet(config.SHEET_STAFF)
    records = safe_get_all_records(ws)
    for row in records:
        if str(row.get("Telegram_ID", "")).strip() == str(telegram_id):
            if str(row.get("Status", "")).strip().lower() == "inactive":
                return None
            return row
    return None


def _next_patient_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("PT"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"PT{next_num:04d}"


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
    if phone_val:
        ws.update_cell(new_row_number, 6, "'" + str(phone_val))
    if alt_phone_val:
        ws.update_cell(new_row_number, 7, "'" + str(alt_phone_val))
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
    ws = _worksheet(conf…8287 tokens truncated…    ws.update_cell(row_number, 6, done)   # Sessions_Done কলাম F
    if total and done >= total:
        ws.update_cell(row_number, 12, "Completed")  # Status কলাম L
    _invalidate_cache(ws)
    return True


def get_daily_register(date_str: str | None = None) -> dict:
    """
    ০৬_Payments শীট থেকে আজকের সব এন্ট্রি নিয়ে Sl/Patient/Session/Bill/Paid/Due/Status
    সহ রেজিস্টার বানায়, দিনশেষের টোটাল হিসাব করে।
    """
    if date_str is None:
        date_str = bd_now().strftime("%Y-%m-%d")
    payments_today = [
        p for p in get_all_payments() if str(p.get("Date", "")).strip() == date_str
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


def get_daily_patient_list(date_str: str) -> list[dict]:
    payments = safe_get_all_records(_worksheet(config.SHEET_PAYMENTS))
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
        monthly_salary = float(staff.get("Salary", 0) or 0)
    except (TypeError, ValueError):
        monthly_salary = 0

    ws = _worksheet(config.SHEET_SALARY)
    records = safe_get_all_records(ws)
    paid = sum(
        float(r.get("Amount", 0) or 0)
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


def add_salary_payment(staff_id: str, month: str, amount: float, paid_by: str, note: str = "") -> str:
    """13_Salary শীটে একটা কিস্তি সেভ করে।"""
    ws = _worksheet(config.SHEET_SALARY)
    payment_id = _next_salary_payment_id(ws)
    now = bd_now()
    row = [
        payment_id,
        now.strftime("%Y-%m-%d"),
        month,
        staff_id,
        amount,
        paid_by,
        now.strftime("%Y-%m-%d %I:%M %p"),
        note,
    ]
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


def add_expense(category: str, amount: float, added_by: str, note: str = "") -> str:
    """07_Expenses শীটে একটা খরচের এন্ট্রি সেভ করে।"""
    ws = _worksheet(config.SHEET_EXPENSES)
    expense_id = _next_expense_id(ws)
    now = bd_now()
    row = [
        expense_id,
        now.strftime("%Y-%m-%d"),
        category,
        amount,
        added_by,
        now.strftime("%Y-%m-%d %I:%M %p"),
        note,
    ]
    _append_unified_row(
        ws, row, "expense", expense_id,
        provider_id=added_by,
    )
    _invalidate_cache(ws)
    return expense_id


def get_expenses_for_date(date_str: str) -> list[dict]:
    """নির্দিষ্ট তারিখের সব খরচের এন্ট্রি রিটার্ন করে (নতুন থেকে পুরনো)। date_str ফরম্যাট: 'YYYY-MM-DD'"""
    ws = _worksheet(config.SHEET_EXPENSES)
    records = safe_get_all_records(ws)
    rows = [r for r in records if str(r.get("Date", "")).strip() == date_str]
    rows.sort(key=lambda r: str(r.get("Timestamp", "")), reverse=True)
    return rows


def get_expense_total_for_month(month: str) -> float:
    """নির্দিষ্ট মাসের মোট খরচ রিটার্ন করে। month ফরম্যাট: 'YYYY-MM'"""
    ws = _worksheet(config.SHEET_EXPENSES)
    records = safe_get_all_records(ws)
    total = sum(
        float(r.get("Amount", 0) or 0)
        for r in records
        if str(r.get("Date", "")).strip().startswith(month)
    )
    return round(total, 2)


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

