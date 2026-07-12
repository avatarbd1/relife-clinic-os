"""
sheets.py
Google Sheets-কে ডেটাবেস হিসেবে ব্যবহার করার জন্য gspread wrapper।
সব read/write এই ফাইলের মধ্য দিয়ে যাবে — bot.py সরাসরি gspread ছুঁবে না,
এতে ভবিষ্যতে ডেটাবেস বদলাতে হলে (যেমন Postgres-এ migrate) শুধু এই ফাইলটাই বদলালেই হবে।
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

_client = None
_spreadsheet = None


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
    return _get_spreadsheet().worksheet(name)


def get_staff_by_telegram_id(telegram_id: int) -> dict | None:
    ws = _worksheet(config.SHEET_STAFF)
    records = ws.get_all_records()
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
    now = datetime.now()

    row = [
        patient_id,
        now.strftime("%Y-%m-%d"),
        now.strftime("%H:%M"),
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
        now.strftime("%Y-%m-%d %H:%M"),
        now.strftime("%Y-%m-%d %H:%M"),
    ]
    ws.append_row(row, value_input_option="RAW")
    return patient_id


def get_all_patients() -> list[dict]:
    ws = _worksheet(config.SHEET_PATIENTS)
    return ws.get_all_records()


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
    return ws.get_all_records()


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
    records = ws.get_all_records()
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
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    attendance_id = _next_attendance_id(ws)

    shift_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
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
    time_str = datetime.now().strftime("%H:%M")
    _update_attendance_cell(record["_row_number"], 7, time_str)
    return time_str


def attendance_break_in(staff_id: str, date_str: str) -> str | None:
    record = get_today_attendance(staff_id, date_str)
    if not record:
        return None
    time_str = datetime.now().strftime("%H:%M")
    _update_attendance_cell(record["_row_number"], 8, time_str)
    return time_str


def attendance_check_out(staff_id: str, date_str: str) -> dict | None:
    record = get_today_attendance(staff_id, date_str)
    if not record:
        return None
    now = datetime.now()
    time_str = now.strftime("%H:%M")

    try:
        check_in = datetime.strptime(f"{date_str} {record.get('Check_In','')}", "%Y-%m-%d %H:%M")
    except ValueError:
        check_in = now

    total_minutes = (now - check_in).total_seconds() / 60

    break_out = record.get("Break_Out", "")
    break_in = record.get("Break_In", "")
    if break_out and break_in:
        try:
            bo = datetime.strptime(f"{date_str} {break_out}", "%Y-%m-%d %H:%M")
            bi = datetime.strptime(f"{date_str} {break_in}", "%Y-%m-%d %H:%M")
            total_minutes -= (bi - bo).total_seconds() / 60
        except ValueError:
            pass

    working_hours = round(total_minutes / 60, 2)
    overtime = round(max(0, working_hours - 8), 2)

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
    ws.update_cell(row_number, 29, datetime.now().strftime("%Y-%m-%d %H:%M"))  # updated_at

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
    return True


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
        datetime.now().strftime("%Y-%m-%d"), status,
    ]
    ws.append_row(row)
    return package_id


def get_active_package_for_patient(patient_id: str) -> dict | None:
    package_sheet_name = getattr(config, "SHEET_PACKAGES", None)
    if not package_sheet_name:
        # প্যাকেজ ফিচার এখনো সেটআপ করা হয়নি (config.py-তে SHEET_PACKAGES নেই) —
        # সাইলেন্টলি None রিটার্ন করে, যাতে Payment ফ্লো ভেঙে না যায়।
        return None
    try:
        ws = _worksheet(package_sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return None
    records = ws.get_all_records()
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
    return True


def add_payment(data: dict) -> str:
    ws = _worksheet(config.SHEET_PAYMENTS)
    receipt_no = _next_receipt_no(ws)
    row = [
        receipt_no,
        datetime.now().strftime("%Y-%m-%d"),
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
