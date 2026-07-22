# -*- coding: utf-8 -*-
"""
Relief bot patch script
------------------------
Fixes 2 things (run this from inside the repo folder, same place as bot.py):

1) তারিখ অনুযায়ী রিপোর্ট (date report) will now show ONLY the patient list
   (like the রোগীর তালিকা style), not the নতুন রোগী/মোট রোগী/পেমেন্ট এন্ট্রি/আয়
   numbers block. Those numbers stay only in রিপোর্ট ও অ্যানালিটিক্স (unchanged).

2) When an appointment is marked "✅ উপস্থিত" (Completed), it now
   automatically creates a matching entry in আজকের রেজিস্টার (daily register),
   so attendance and the register stay in sync.

Usage (inside repo folder):
    python3 patch_relief.py
"""

import io
import sys

def patch_file(path, replacements):
    with io.open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new, label in replacements:
        count = content.count(old)
        if count == 0:
            print(f"⚠️  SKIP [{path}] '{label}' — matching text not found (already patched, or file changed). Check manually.")
            continue
        if count > 1:
            print(f"⚠️  WARNING [{path}] '{label}' — found {count} times, replacing all.")
        content = content.replace(old, new)
        print(f"✅ Patched [{path}] '{label}'")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# sheets.py — add 2 helper functions
# ---------------------------------------------------------------------------
SHEETS_OLD_1 = '''def update_appointment_status(appointment_id: str, status: str) -> bool:
    ws = _worksheet(config.SHEET_APPOINTMENTS)
    cell = ws.find(appointment_id)
    if cell is None:
        return False
    ws.update_cell(cell.row, 8, status)
    return True'''

SHEETS_NEW_1 = '''def update_appointment_status(appointment_id: str, status: str) -> bool:
    ws = _worksheet(config.SHEET_APPOINTMENTS)
    cell = ws.find(appointment_id)
    if cell is None:
        return False
    ws.update_cell(cell.row, 8, status)
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
    return False'''


# ---------------------------------------------------------------------------
# bot.py — 1) auto-create register entry on "উপস্থিত"
# ---------------------------------------------------------------------------
BOT_OLD_1 = '''async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, appointment_id, status_code = query.data.split("_", 2)
    status_map = {"Completed": "Completed", "NoShow": "No-show"}
    status = status_map.get(status_code, status_code)
    ok = sheets.update_appointment_status(appointment_id, status)
    if ok:
        await query.edit_message_text(f"✅ {appointment_id} — স্ট্যাটাস: {status}")
    else:
        await query.edit_message_text("❌ আপডেট করা যায়নি।")'''

BOT_NEW_1 = '''async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, appointment_id, status_code = query.data.split("_", 2)
    status_map = {"Completed": "Completed", "NoShow": "No-show"}
    status = status_map.get(status_code, status_code)
    ok = sheets.update_appointment_status(appointment_id, status)
    if not ok:
        await query.edit_message_text("❌ আপডেট করা যায়নি।")
        return

    reply_lines = [f"✅ {appointment_id} — স্ট্যাটাস: {status}"]

    if status_code == "Completed":
        appt = sheets.get_appointment_by_id(appointment_id)
        if appt:
            appt_date = appt.get("Date", "") or bd_now().strftime("%Y-%m-%d")
            if not sheets.has_payment_for_appointment(appointment_id, appt_date):
                staff = context.user_data.get("staff") or sheets.get_staff_by_telegram_id(update.effective_user.id)
                try:
                    sheets.add_payment({
                        "Patient_ID": appt.get("Patient_ID", ""),
                        "Patient_Name": appt.get("Patient_Name", ""),
                        "Department": appt.get("Department", ""),
                        "Amount": 0,
                        "Discount": 0,
                        "Due": 0,
                        "Payment_Method": "",
                        "Received_By": staff.get("Full_Name", "Unknown") if staff else "Unknown",
                        "Remarks": f"Sessions: 1 | APT:{appointment_id}",
                    })
                    reply_lines.append("📋 দৈনিক রেজিস্টারে এন্ট্রি যোগ হয়েছে।")
                except Exception:
                    logger.exception("Appointment থেকে রেজিস্টার এন্ট্রি যোগ করতে ব্যর্থ")

    await query.edit_message_text("\\n".join(reply_lines))'''


# ---------------------------------------------------------------------------
# bot.py — 2) date report: patient list only
# ---------------------------------------------------------------------------
BOT_OLD_2 = '''async def date_report_day_selected(update, context):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_", 1)[1]
    year, month, day = map(int, date_str.split("-"))

    daily = sheets.get_daily_report(date_str)
    monthly = sheets.get_month_running_total(year, month, day)

    import calendar as _cal
    text = (
        f"📅 {date_str} — দিনের হিসাব\\n"
        f"🆕 নতুন রোগী রেজিস্ট্রেশন: {daily[\'patient_count\']}\\n"
        f"🧍 মোট রোগী (ভিজিট): {daily[\'total_patients_today\']}\\n"
        f"💳 পেমেন্ট এন্ট্রি: {daily[\'payment_count\']}\\n"
        f"💰 আয়: {daily[\'total_income\']:.0f} টাকা\\n\\n"
        f"📊 {_cal.month_name[month]} {year} — মাসের রানিং টোটাল (১–{day} তারিখ)\\n"
        f"🆕 নতুন রোগী: {monthly[\'patient_count\']}\\n"
        f"🧍 মোট রোগী (ভিজিট): {monthly[\'total_patients_month\']}\\n"
        f"💳 পেমেন্ট এন্ট্রি: {monthly[\'payment_count\']}\\n"
        f"💰 মোট আয়: {monthly[\'total_income\']:.0f} টাকা"
    )
    patient_list = sheets.get_daily_patient_list(date_str)
    if patient_list:
        list_lines = "\\n".join(
            f"{i+1}. {p[\'name\']} — {p[\'session\']} — {p[\'amount\']:.0f} টাকা"
            for i, p in enumerate(patient_list)
        )
        text += f"\\n\\n📋 রোগীর তালিকা:\\n{list_lines}"

    await query.edit_message_text(text, reply_markup=calendar_helper.build_calendar(year, month))'''

BOT_NEW_2 = '''async def date_report_day_selected(update, context):
    query = update.callback_query
    await query.answer()
    date_str = query.data.split("_", 1)[1]
    year, month, day = map(int, date_str.split("-"))

    patient_list = sheets.get_daily_patient_list(date_str)
    if patient_list:
        list_lines = "\\n".join(
            f"{i+1}. {p[\'name\']} — {p[\'session\']} — {p[\'amount\']:.0f} টাকা"
            for i, p in enumerate(patient_list)
        )
        text = f"📋 {date_str} — রোগীর তালিকা:\\n{list_lines}"
    else:
        text = f"📋 {date_str} — এই তারিখে কোনো রোগীর এন্ট্রি পাওয়া যায়নি।"

    await query.edit_message_text(text, reply_markup=calendar_helper.build_calendar(year, month))'''


def main():
    patch_file("sheets.py", [
        (SHEETS_OLD_1, SHEETS_NEW_1, "get_appointment_by_id / has_payment_for_appointment"),
    ])
    patch_file("bot.py", [
        (BOT_OLD_1, BOT_NEW_1, "apt_status_callback -> auto register entry"),
        (BOT_OLD_2, BOT_NEW_2, "date_report_day_selected -> patient list only"),
    ])
    print("")
    print("ডান — এখন চেক করো: python3 -m py_compile bot.py sheets.py")


if __name__ == "__main__":
    main()

