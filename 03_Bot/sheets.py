"""
sheets.py
Google Sheets-কে ডেটাবেস হিসেবে ব্যবহার করার জন্য gspread wrapper।
সব read/write এই ফাইলের মধ্য দিয়ে যাবে — bot.py সরাসরি gspread ছুঁবে না,
এতে ভবিষ্যতে ডেটাবেস বদলাতে হলে (যেমন Postgres-এ migrate) শুধু এই ফাইলটাই বদলালেই হবে।
"""

import json
import gspread
import re

import time

_records_cache = {}  # {worksheet_title: (timestamp, records)}
_RECORDS_CACHE_TTL = 2.0  # সেকেন্ড — একই ড্যাশবোর্ড রেন্ডারের মধ্যে বারবার একই শীট না পড়ার জন্য


def safe_get_all_records(ws, _retries: int = 2, _use_cache: bool = True):
    """get_all_records()-এর নিরাপদ ভার্সন — sheet-এ শুধু header বা কোনো row না থাকলে crash না করে খালি list রিটার্ন করে।
    Google Sheets rate-limit/temporary error হলে ১-২ বার retry করে, যাতে দ্রুত পরপর ক্লিকে
    ভুল করে 'কিছুই নেই' না দেখায়। কয়েক সেকেন্ডের জন্য ফলাফল ক্যাশে রাখে যাতে একই Dashboard
    রেন্ডারের মধ্যে (যেখানে অনেক রোগীর জন্য বারবার একই শীট পড়া লাগে) API কল কম হয় এবং দ্রুত হয়।"""
    cache_key = ws.title
    if _use_cache and cache_key in _records_cache:
        ts, cached = _records_cache[cache_key]
        if time.time() - ts < _RECORDS_CACHE_TTL:
            return cached
    try:
        if ws.row_count < 2:
            result = []
        else:
            first_row = ws.row_values(1)
            result = [] if not first_row else ws.get_all_records()
        _records_cache[cache_key] = (time.time(), result)
        return result
    except gspread.exceptions.APIError as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if _retries > 0 and status in (429, 500, 503):
            time.sleep(1.5)
            return safe_get_all_records(ws, _retries - 1, _use_cache)
        return []
    except Exception:
        return []


def _invalidate_cache(ws) -> None:
    """কোনো শীটে write (append/update) হওয়ার পর সেই শীটের cache মুছে দেয়, যাতে সাথে সাথে
    করা পরবর্তী read পুরনো (stale) ডেটা না দেখায়।"""
    _records_cache.pop(ws.title, None)


from google.oauth2.service_account import Credentials
from datetime import datetime

import config
from config import bd_now

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client = None
_spreadsheet = None
_worksheet_cache = {}


def _get_client():
    global _client
    if _client is None:
        creds = Credentials.from_service_account_file(
            config.GOOGLE_CREDENTIALS_PATH, scopes=SCOPES
        )
        _client = gspread.authorize(creds)
    return _client


def _get_spreadsheet():
    global _spreadsheet
    if _spreadsheet is None:
        _spreadsheet = _get_client().open_by_key(config.GOOGLE_SHEET_ID)
    return _spreadsheet


def _worksheet(name: str):
    if name not in _worksheet_cache:
        _worksheet_cache[name] = _get_spreadsheet().worksheet(name)
    return _worksheet_cache[name]


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
    ws.append_row(row, value_input_option="RAW")
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
    ws.append_row(row, value_input_option="RAW")
    return appointment_id


def get_all_appointments() -> list[dict]:
    ws = _worksheet(config.SHEET_APPOINTMENTS)
    return safe_get_all_records(ws)


def get_appointments_for_date(date_str: str) -> list[dict]:
    all_appts = get_all_appointments()
    return [a for a in all_appts if str(a.get("Date", "")).strip() == date_str.strip()]


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


def attendance_check_in(staff: dict) -> str:
    ws = _worksheet(config.SHEET_ATTENDANCE)
    now = bd_now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%I:%M %p")
    attendance_id = _next_attendance_id(ws)

    shift_start = now.replace(hour=8, minute=45, second=0, microsecond=0)
    late_min = max(0, int((now - shift_start).total_seconds() // 60))
    status = "Late" if late_min > 15 else "Present"

    staff_id = staff.get("Staff_ID", "") or str(staff.get("Telegram_ID", ""))
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
        "",
    ]
    ws.append_row(row, value_input_option="RAW")
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

    _update_attendance_cell(record["_row_number"], 9, time_str)
    _update_attendance_cell(record["_row_number"], 10, working_hours)
    _update_attendance_cell(record["_row_number"], 12, overtime)

    return {"time": time_str, "working_hours": working_hours, "overtime": overtime}


def get_patient_by_id(patient_id: str) -> dict | None:
    """একটা নির্দিষ্ট Patient_ID দিয়ে রোগীর সম্পূর্ণ তথ্য বের করে।"""
    patient_id = patient_id.strip()
    for p in get_all_patients():
        if str(p.get("Patient_ID", "")).strip() == patient_id:
            return p
    return None


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

    ws.update_cell(row_number, 20, status)      # Payment_Status
    ws.update_cell(row_number, 22, new_paid)    # Paid_Amount
    ws.update_cell(row_number, 23, new_due)     # Due_Amount
    ws.update_cell(row_number, 29, bd_now().strftime("%Y-%m-%d %I:%M %p"))  # updated_at

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


def get_appointment_by_id(appointment_id: str) -> dict | None:
    """Appointment_ID দিয়ে একটা নির্দিষ্ট অ্যাপয়েন্টমেন্ট খুঁজে বের করে।"""
    for a in get_all_appointments():
        if str(a.get("Appointment_ID", "")).strip() == str(appointment_id).strip():
            return a
    return None


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
    ws.append_row(row)
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
    ws.update_cell(row_number, 8, paid_amount)
    ws.update_cell(row_number, 9, due_amount)
    return True


def increment_package_session(patient_id: str) -> bool:
    pkg = get_active_package_for_patient(patient_id)
    if pkg is None:
        return False
    ws = _worksheet(config.SHEET_PACKAGES)
    used = int(pkg.get("Sessions_Used", 0)) + 1
    total = int(pkg.get("Total_Sessions", 0))
    remaining = max(0, total - used)
    row_number = pkg["_row_number"]
    ws.update_cell(row_number, 5, used)
    ws.update_cell(row_number, 6, remaining)
    if remaining == 0:
        ws.update_cell(row_number, 11, "Completed")
    _invalidate_cache(ws)
    return True


def decrement_package_session(patient_id: str) -> bool:
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
    used = max(0, int(pkg.get("Sessions_Used", 0) or 0) - 1)
    total = int(pkg.get("Total_Sessions", 0) or 0)
    remaining = max(0, total - used)
    ws.update_cell(row_number, 5, used)
    ws.update_cell(row_number, 6, remaining)
    if remaining > 0 and str(pkg.get("Status", "")).strip() == "Completed":
        ws.update_cell(row_number, 11, "Active")
    _invalidate_cache(ws)
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
    ws.append_row(row)
    return receipt_no


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
        for _ in range(sessions):
            try:
                decrement_package_session(patient_id)
            except Exception as e:
                print(f"⚠️ প্যাকেজ সেশন রিভার্স করতে সমস্যা হয়েছে: {e}")
                break

    # ৪) Delete_Log শীটে রেকর্ড রাখা
    try:
        log_ws = _worksheet(getattr(config, "SHEET_DELETE_LOG", "Delete_Log"))
        log_ws.append_row([
            bd_now().strftime("%Y-%m-%d %I:%M %p"),
            deleted_by,
            "Payment/Session",
            entry["Receipt_No"],
            entry["Patient_ID"],
            entry["Patient_Name"],
            entry["Amount"],
            sessions,
            json.dumps(entry, ensure_ascii=False),
        ])
    except Exception as e:
        print(f"⚠️ Delete_Log-এ লেখা ব্যর্থ হয়েছে (এন্ট্রি তবুও মোছা হয়েছে): {e}")

    return entry


def get_all_payments() -> list[dict]:
    ws = _worksheet(config.SHEET_PAYMENTS)
    return safe_get_all_records(ws)


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
    ws.append_row(row, value_input_option="RAW")
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
    ws.append_row(row, value_input_option="RAW")
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
    ws.update_cell(row_number, 6, done)   # Sessions_Done কলাম F
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
    ws.append_row(row, value_input_option="RAW")
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
    ws.append_row(row, value_input_option="RAW")
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
