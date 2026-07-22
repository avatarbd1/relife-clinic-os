# -*- coding: utf-8 -*-
"""
Relief bot patch 2 — bot.py
----------------------------
sheets.py আগেই ঠিক হয়ে গেছে (get_appointment_by_id / has_payment_for_appointment)।
এই প্যাচ শুধু bot.py-এর apt_status_callback ফাংশনে register-entry যোগ করে,
patch1.py-এর Patient Action Panel অংশ অক্ষত রেখে।

Run from ~/relife-clinic-os/03_Bot (যেখানে bot.py আছে):
    python3 patch2_relief.py
"""

import io
import sys


def patch_file(path, replacements):
    with io.open(path, "r", encoding="utf-8") as f:
        content = f.read()
    for old, new, label in replacements:
        count = content.count(old)
        if count == 0:
            print(f"❌ SKIP [{path}] '{label}' — matching text not found.")
            continue
        if count > 1:
            print(f"⚠️  WARNING [{path}] '{label}' — found {count} times, replacing all.")
        content = content.replace(old, new)
        print(f"✅ Patched [{path}] '{label}'")
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(content)


BOT_OLD = '''async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_", 3)
    appointment_id = parts[1]
    status_code = parts[2]
    patient_id = parts[3] if len(parts) > 3 else ""
    status_map = {"Completed": "Completed", "NoShow": "No-show"}
    status = status_map.get(status_code, status_code)
    ok = sheets.update_appointment_status(appointment_id, status)
    if not ok:
        await query.edit_message_text("❌ আপডেট করা যায়নি।")
        return

    if status_code == "Completed" and patient_id:
        # Present চাপার পরপরই Patient Action Panel — Payment/Note এখন ১ ট্যাপ দূরে।
        patient = sheets.get_patient_by_id(patient_id)
        if patient:
            await query.edit_message_text(
                f"✅ {appointment_id} — উপস্থিতি হয়েছে।\\n\\n" + _patient_card_text(patient),
                reply_markup=_patient_card_keyboard(patient_id),
            )
            return

    await query.edit_message_text(f"✅ {appointment_id} — সূচি ও: {status}")'''

BOT_NEW = '''async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_", 3)
    appointment_id = parts[1]
    status_code = parts[2]
    patient_id = parts[3] if len(parts) > 3 else ""
    status_map = {"Completed": "Completed", "NoShow": "No-show"}
    status = status_map.get(status_code, status_code)
    ok = sheets.update_appointment_status(appointment_id, status)
    if not ok:
        await query.edit_message_text("❌ আপডেট করা যায়নি।")
        return

    if status_code == "Completed":
        # উপস্থিত হলে দৈনিক রেজিস্টারে (Payments শীট) একটা এন্ট্রি অটো যোগ হবে,
        # যাতে "আজকের রেজিস্টার" আর "তারিখ অনুযায়ী রিপোর্ট"-এ দেখা যায়।
        today_str = bd_now().strftime("%Y-%m-%d")
        if not sheets.has_payment_for_appointment(appointment_id, today_str):
            appt = sheets.get_appointment_by_id(appointment_id)
            reg_patient_id = patient_id or (appt.get("Patient_ID", "") if appt else "")
            reg_patient_name = appt.get("Patient_Name", "") if appt else ""
            reg_department = appt.get("Department", "") if appt else ""
            staff = context.user_data.get("staff") or sheets.get_staff_by_telegram_id(update.effective_user.id)
            try:
                sheets.add_payment({
                    "Patient_ID": reg_patient_id,
                    "Patient_Name": reg_patient_name,
                    "Department": reg_department,
                    "Amount": 0,
                    "Discount": 0,
                    "Due": 0,
                    "Payment_Method": "",
                    "Received_By": staff.get("Full_Name", "Unknown") if staff else "Unknown",
                    "Remarks": f"Sessions: 1 | APT:{appointment_id}",
                })
            except Exception:
                logger.exception("Appointment থেকে রেজিস্টার এন্ট্রি যোগ করতে ব্যর্থ")

    if status_code == "Completed" and patient_id:
        # Present চাপার পরপরই Patient Action Panel — Payment/Note এখন ১ ট্যাপ দূরে।
        patient = sheets.get_patient_by_id(patient_id)
        if patient:
            await query.edit_message_text(
                f"✅ {appointment_id} — উপস্থিতি হয়েছে।\\n\\n" + _patient_card_text(patient),
                reply_markup=_patient_card_keyboard(patient_id),
            )
            return

    await query.edit_message_text(f"✅ {appointment_id} — সূচি ও: {status}")'''


def main():
    patch_file("bot.py", [
        (BOT_OLD, BOT_NEW, "apt_status_callback -> auto register entry (Patient Action Panel version)"),
    ])
    print("")
    print("এখন চেক করো: python3 -m py_compile bot.py sheets.py")


if __name__ == "__main__":
    main()

