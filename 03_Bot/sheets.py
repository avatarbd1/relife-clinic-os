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
    records = ws.get_all_records()

    for r in records:
        phone = str(r.get("Phone", "")).strip()
        if phone.isdigit() and len(phone) == 10:
            r["Phone"] = "0" + phone

        alt = str(r.get("Alternative_Phone", "")).strip()
        if alt.isdigit() and len(alt) == 10:
            r["Alternative_Phone"] = "0" + alt

    return records

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

def _next_daily_sl(ws, date_str: str) -> int:
    """সেই তারিখে এখন পর্যন্ত কতগুলো পেমেন্ট এন্ট্রি হয়েছে তা গুনে পরের SL নম্বর দেয়।"""
    try:
        records = ws.get_all_records()
    except Exception:
        return 1
    count = sum(1 for r in records if str(r.get("Date", "")) == date_str)
    return count + 1

def add_payment(data: dict) -> str:
    ws = _worksheet(config.SHEET_PAYMENTS)
    receipt_no = _next_receipt_no(ws)
    date_str = datetime.now().strftime("%Y-%m-%d")
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

def get_all_payments() -> list[dict]:
    ws = _worksheet(config.SHEET_PAYMENTS)
    return ws.get_all_records()

def get_payments_for_patient(patient_id: str) -> list[dict]:
    all_payments = get_all_payments()
    return [p for p in all_payments if str(p.get("Patient_ID", "")).strip() == str(patient_id).strip()]

def get_appointments_for_patient(patient_id: str) -> list[dict]:
    all_apts = get_all_appointments()
    return [a for a in all_apts if str(a.get("Patient_ID", "")).strip() == str(patient_id).strip()]

def get_treatment_notes_for_patient(patient_id: str) -> list[dict]:
    ws = _worksheet(config.SHEET_TREATMENTS)
    all_notes = ws.get_all_records()
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

def add_treatment_note(data: dict, created_by: str) -> str:
    """
    05_Treatments শীটে নতুন ট্রিটমেন্ট নোট যোগ করে।
    Phase A fix: শীটে 'Machines' কলাম থাকলে persist করে।
    """
    ws = _worksheet(config.SHEET_TREATMENTS)
    treatment_id = _next_treatment_id(ws)
    base_row = [
        treatment_id,
        datetime.now().strftime("%Y-%m-%d"),
        data.get("Patient_ID", ""),
        data.get("Patient_Name", ""),
        data.get("Diagnosis", ""),
        data.get("Treatment_Given", ""),
        data.get("Exercise", ""),
        data.get("Electrotherapy", ""),
        data.get("Manual_Therapy", ""),
        data.get("Session_No", ""),
        created_by,
        data.get("Remarks", ""),
        data.get("Plan_ID", ""),
    ]
    try:
        headers = [h.strip() for h in ws.row_values(1)]
        if "Machines" in headers:
            base_row.append(data.get("Machines", ""))
    except Exception:
        pass
    ws.append_row(base_row, value_input_option="RAW")
    return treatment_id

def get_last_treatment_snapshot(patient_id: str) -> dict | None:
    """
    "✅ গতকালের মতোই" feature-এর জন্য শেষ treatment note-এর
    reusable fields ফেরত দেয়।
    """
    last = get_last_treatment_note_for_patient(patient_id)
    if not last:
        return None
    return {
        "Diagnosis": last.get("Diagnosis", ""),
        "Treatment_Given": last.get("Treatment_Given", ""),
        "Exercise": last.get("Exercise", ""),
        "Electrotherapy": last.get("Electrotherapy", ""),
        "Manual_Therapy": last.get("Manual_Therapy", ""),
        "Machines": last.get("Machines", ""),
        "Session_No": last.get("Session_No", ""),
        "Date": last.get("Date", ""),
    }

def get_next_session_no(patient_id: str) -> int:
    """
    Phase D: session number auto-calc।
    v1 rule: Completed appointment count + 1।
    Fallback: treatment note count + 1।
    """
    count = sum(
        1
        for a in get_appointments_for_patient(patient_id)
        if str(a.get("Status", "")).strip() == "Completed"
    )
    if count == 0:
        count = len(get_treatment_notes_for_patient(patient_id))
    return count + 1

def get_recent_patients(limit: int = 6, therapist_name: str | None = None) -> list[dict]:
    """
    Phase B: সাম্প্রতিক activity অনুযায়ী quick-pick patient list।
    Treatment note + appointment উভয় দেখে সর্বশেষ active date বের করে।
    """
    seen: dict[str, str] = {}

    # treatment notes থেকে
    try:
        tr_ws = _worksheet(config.SHEET_TREATMENTS)
        for r in tr_ws.get_all_records():
            pid = str(r.get("Patient_ID", "")).strip()
            d = str(r.get("Date", "")).strip()
            if pid and d > seen.get(pid, ""):
                seen[pid] = d
    except Exception:
        pass

    # appointments থেকে
    for r in get_all_appointments():
        pid = str(r.get("Patient_ID", "")).strip()
        d = str(r.get("Date", "")).strip()
        if pid and d > seen.get(pid, ""):
            seen[pid] = d

    sorted_pids = sorted(seen, key=lambda p: seen[p], reverse=True)

    results: list[dict] = []
    for pid in sorted_pids:
        if len(results) >= limit:
            break
        patient = get_patient_by_id(pid)
        if not patient or str(patient.get("Status", "")).strip() != "Active":
            continue
        if therapist_name and str(patient.get("Therapist", "")).strip() != therapist_name.strip():
            continue
        patient["_last_date"] = seen[pid]
        results.append(patient)
    return results

def add_appointments_bulk(rows: list[dict], created_by: str) -> list[str]:
    """
    Phase E: multi-day booking — একই রোগীর জন্য একাধিক date-এ
    appointment row একসাথে insert করে।
    """
    ws = _worksheet(config.SHEET_APPOINTMENTS)
    ids: list[str] = []
    for data in rows:
        appt_id = _next_appointment_id(ws)
        row = [
            appt_id,
            data.get("Date", ""),
            data.get("Time", ""),
            data.get("Patient_ID", ""),
            data.get("Patient_Name", ""),
            data.get("Department", ""),
            data.get("Therapist", ""),
            "Scheduled",
            data.get("Remarks", created_by),
        ]
        ws.append_row(row, value_input_option="RAW")
        ids.append(appt_id)
    return ids

def update_next_visit_from_dates(patient_id: str, selected_dates: list[str]) -> str | None:
    """
    Phase F: selected_dates-এর মধ্যে আজ বা পরে সবচেয়ে কাছের date
    02_Patients.Next_Visit-এ লেখে।
    """
    from datetime import date as _date, datetime as _dt

    if not selected_dates:
        return None

    today = _date.today()
    upcoming = []
    for ds in selected_dates:
        try:
            upcoming.append(_dt.strptime(ds.strip(), "%Y-%m-%d").date())
        except ValueError:
            pass

    upcoming = [d for d in upcoming if d >= today]
    if not upcoming:
        return None

    nearest = min(upcoming).strftime("%Y-%m-%d")
    return nearest if update_next_visit(patient_id, nearest) else None

def update_next_visit(
patient_id: str, next_visit_date: str) -> bool:
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
        datetime.now().strftime("%Y-%m-%d"),
        "Active",
    ]
    ws.append_row(row, value_input_option="RAW")
    return plan_id

def get_active_plan_for_patient(patient_id: str) -> dict | None:
    """রোগীর বর্তমান Active ট্রিটমেন্ট প্ল্যান ফেরত দেয় (থাকলে), না থাকলে None।"""
    ws = _worksheet(config.SHEET_TREATMENT_PLANS)
    records = ws.get_all_records()
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
    records = ws.get_all_records()
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
    return True
