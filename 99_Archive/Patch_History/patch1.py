#!/usr/bin/env python3
"""
Patch 1 — Relife Clinic OS bot.py
- Shared Patient Action Panel reused after: Present (✅), Full History, Treatment History date-view
- Kills the 100% duplicate history-building code (hist_select_callback / plist_action_hist)
- Fixes "🔙 তালিকায় ফিরুন" so it never dead-ends when opened from a non-list flow

Run from the folder containing bot.py:
    python patch1.py
It edits bot.py in place. Safe to re-run only once (it will error out cleanly if
already applied, instead of corrupting the file).
"""
import re
import sys

PATH = "bot.py"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

original_src = src


def replace_once(old, new, label):
    global src
    count = src.count(old)
    if count == 0:
        print(f"❌ FAILED to locate block for: {label}")
        print("   (bot.py may already be patched, or has changed since this patch was written)")
        sys.exit(1)
    if count > 1:
        print(f"❌ Block for '{label}' is not unique ({count} matches) — aborting to avoid a bad edit.")
        sys.exit(1)
    src = src.replace(old, new, 1)
    print(f"✅ applied: {label}")


# ---------------------------------------------------------------------------
# 1) today_appointments — embed Patient_ID in the "Present/No-show" callback_data
#    so apt_status_callback can open the Action Panel without extra Sheet reads.
# ---------------------------------------------------------------------------
replace_once(
    old='''        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ উপস্থিত", callback_data=f"aptstatus_{a.get('Appointment_ID')}_Completed"),
            InlineKeyboardButton("❌ আসেনি", callback_data=f"aptstatus_{a.get('Appointment_ID')}_NoShow"),
        ]])''',
    new='''        buttons = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ উপস্থিত", callback_data=f"aptstatus_{a.get('Appointment_ID')}_Completed_{a.get('Patient_ID')}"),
            InlineKeyboardButton("❌ আসেনি", callback_data=f"aptstatus_{a.get('Appointment_ID')}_NoShow_{a.get('Patient_ID')}"),
        ]])''',
    label="today_appointments: add Patient_ID to aptstatus_ callback_data",
)

# ---------------------------------------------------------------------------
# 2) apt_status_callback — after "✅ উপস্থিত" (Present), auto-open the
#    Patient Action Panel instead of a dead-end confirmation text.
# ---------------------------------------------------------------------------
replace_once(
    old='''async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, appointment_id, status_code = query.data.split("_", 2)
    status_map = {"Completed": "Completed", "NoShow": "No-show"}
    status = status_map.get(status_code, status_code)
    ok = sheets.update_appointment_status(appointment_id, status)
    if ok:
        await query.edit_message_text(f"✅ {appointment_id} — স্ট্যাটাস: {status}")
    else:
        await query.edit_message_text("❌ আপডেট করা যায়নি।")''',
    new='''async def apt_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
                f"✅ {appointment_id} — উপস্থিত হয়েছে।\\n\\n" + _patient_card_text(patient),
                reply_markup=_patient_card_keyboard(patient_id),
            )
            return

    await query.edit_message_text(f"✅ {appointment_id} — স্ট্যাটাস: {status}")''',
    label="apt_status_callback: auto-open Action Panel after Present",
)

# ---------------------------------------------------------------------------
# 3) New shared helper: _build_full_history_text()
#    Replaces the 100% duplicate logic that lived separately in
#    hist_select_callback() and plist_action_hist().
# ---------------------------------------------------------------------------
replace_once(
    old='''async def hist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):''',
    new='''def _build_full_history_text(patient_id: str) -> str | None:
    """রোগীর সম্পূর্ণ ইতিহাস (প্রোফাইল + পেমেন্ট + অ্যাপয়েন্টমেন্ট + ট্রিটমেন্ট নোট) টেক্সট বানায়।
    আগে hist_select_callback() আর plist_action_hist() -এ এই একই কোড হুবহু দুইবার লেখা ছিল —
    এখন দুটোই এই একটামাত্র ফাংশন কল করে, তাই এক জায়গায় ফিক্স করলেই দুই জায়গায় কাজ করবে।"""
    patient = sheets.get_patient_by_id(patient_id)
    if patient is None:
        return None

    name = patient.get("Full_Name") or patient.get("Name") or "Unknown"
    lines = [f"📜 {name} ({patient_id})-এর ইতিহাস", ""]

    lines.append("👤 প্রোফাইল:")
    lines.append(f"  ফোন: {patient.get('Phone', 'N/A')}")
    lines.append(f"  ঠিকানা: {patient.get('Address', 'N/A')}")
    note = patient.get("Note") or patient.get("Notes") or patient.get("Problem", "")
    if note:
        lines.append(f"  নোট: {note}")
    therapist = patient.get("Therapist", "")
    if therapist:
        lines.append(f"  থেরাপিস্ট: {therapist}")
    lines.append("")

    package = sheets.get_active_package_for_patient(patient_id)
    if package:
        total = package.get("Total_Sessions", "N/A")
        done = package.get("Sessions_Completed", "N/A")
        lines.append(f"🗓️ সেশন: {done} সম্পন্ন / {total} মোট")
        lines.append("")

    payments = sheets.get_payments_for_patient(patient_id)
    if payments:
        lines.append("💳 পেমেন্ট হিস্টরি:")
        total_paid = 0.0
        last_due = 0.0
        for p in payments:
            date_str = p.get("Date", "")
            amount = float(p.get("Amount", 0) or 0)
            due = float(p.get("Due", 0) or 0)
            method = p.get("Payment_Method", "")
            total_paid += amount
            last_due = due
            lines.append(f"  • {date_str}: {amount:.0f} টাকা ({method})")
        lines.append("")
        lines.append(f"💰 সর্বমোট জমা: {total_paid:.0f} টাকা")
        lines.append(f"⏳ সর্বশেষ বাকি: {last_due:.0f} টাকা")
    else:
        lines.append("💳 কোনো পেমেন্ট রেকর্ড নেই।")
    lines.append("")

    appointments = sheets.get_appointments_for_patient(patient_id)
    if appointments:
        lines.append("📅 অ্যাপয়েন্টমেন্ট হিস্টরি:")
        for a in appointments[-10:]:
            date_str = a.get("Date", "")
            status = a.get("Status", "")
            lines.append(f"  • {date_str}: {status}")
    else:
        lines.append("📅 কোনো অ্যাপয়েন্টমেন্ট রেকর্ড নেই।")
    lines.append("")

    treatment_notes = sheets.get_treatment_notes_for_patient(patient_id)
    if treatment_notes:
        lines.append("📝 ট্রিটমেন্ট নোট:")
        for t in treatment_notes[-5:]:
            date_str = t.get("Date", "")
            note_text = t.get("Note", "") or t.get("Notes", "")
            lines.append(f"  • {date_str}: {note_text}")
    else:
        lines.append("📝 কোনো ট্রিটমেন্ট নোট নেই।")

    full_text = "\\n".join(lines)
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "\\n...(আরও আছে)"
    return full_text


async def hist_start(update: Update, context: ContextTypes.DEFAULT_TYPE):''',
    label="add shared _build_full_history_text() helper before hist_start",
)

# ---------------------------------------------------------------------------
# 4) hist_select_callback — use the shared helper + attach Action Panel
#    (fixes the dead-end noted in the audit: this screen had zero buttons).
# ---------------------------------------------------------------------------
replace_once(
    old='''async def hist_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("histsel_", "", 1)

    patient = sheets.get_patient_by_id(patient_id)
    if patient is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    name = patient.get("Full_Name") or patient.get("Name") or "Unknown"
    lines = [f"📜 {name} ({patient_id})-এর ইতিহাস", ""]

    lines.append("👤 প্রোফাইল:")
    lines.append(f"  ফোন: {patient.get('Phone', 'N/A')}")
    lines.append(f"  ঠিকানা: {patient.get('Address', 'N/A')}")
    note = patient.get("Note") or patient.get("Notes") or patient.get("Problem", "")
    if note:
        lines.append(f"  নোট: {note}")
    therapist = patient.get("Therapist", "")
    if therapist:
        lines.append(f"  থেরাপিস্ট: {therapist}")
    lines.append("")

    package = sheets.get_active_package_for_patient(patient_id)
    if package:
        total = package.get("Total_Sessions", "N/A")
        done = package.get("Sessions_Completed", "N/A")
        lines.append(f"🗓️ সেশন: {done} সম্পন্ন / {total} মোট")
        lines.append("")

    payments = sheets.get_payments_for_patient(patient_id)
    if payments:
        lines.append("💳 পেমেন্ট হিস্টরি:")
        total_paid = 0.0
        last_due = 0.0
        for p in payments:
            date_str = p.get("Date", "")
            amount = float(p.get("Amount", 0) or 0)
            due = float(p.get("Due", 0) or 0)
            method = p.get("Payment_Method", "")
            total_paid += amount
            last_due = due
            lines.append(f"  • {date_str}: {amount:.0f} টাকা ({method})")
        lines.append("")
        lines.append(f"💰 সর্বমোট জমা: {total_paid:.0f} টাকা")
        lines.append(f"⏳ সর্বশেষ বাকি: {last_due:.0f} টাকা")
    else:
        lines.append("💳 কোনো পেমেন্ট রেকর্ড নেই।")
    lines.append("")

    appointments = sheets.get_appointments_for_patient(patient_id)
    if appointments:
        lines.append("📅 অ্যাপয়েন্টমেন্ট হিস্টরি:")
        for a in appointments[-10:]:
            date_str = a.get("Date", "")
            status = a.get("Status", "")
            lines.append(f"  • {date_str}: {status}")
    else:
        lines.append("📅 কোনো অ্যাপয়েন্টমেন্ট রেকর্ড নেই।")
    lines.append("")

    treatment_notes = sheets.get_treatment_notes_for_patient(patient_id)
    if treatment_notes:
        lines.append("📝 ট্রিটমেন্ট নোট:")
        for t in treatment_notes[-5:]:
            date_str = t.get("Date", "")
            note_text = t.get("Note", "") or t.get("Notes", "")
            lines.append(f"  • {date_str}: {note_text}")
    else:
        lines.append("📝 কোনো ট্রিটমেন্ট নোট নেই।")

    full_text = "\\n".join(lines)
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "\\n...(আরও আছে)"

    await query.edit_message_text(full_text)
    return ConversationHandler.END''',
    new='''async def hist_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("histsel_", "", 1)

    full_text = _build_full_history_text(patient_id)
    if full_text is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    await query.edit_message_text(full_text, reply_markup=_patient_card_keyboard(patient_id))
    return ConversationHandler.END''',
    label="hist_select_callback: dedupe + attach Action Panel",
)

# ---------------------------------------------------------------------------
# 5) plist_action_hist — same dedupe + Action Panel (it was the exact
#    duplicate of hist_select_callback's old body).
# ---------------------------------------------------------------------------
replace_once(
    old='''async def plist_action_hist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_hist_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if patient is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return

    name = patient.get("Full_Name") or patient.get("Name") or "Unknown"
    lines = [f"📜 {name} ({patient_id})-এর ইতিহাস", ""]
    lines.append("👤 প্রোফাইল:")
    lines.append(f"  ফোন: {patient.get('Phone', 'N/A')}")
    lines.append(f"  ঠিকানা: {patient.get('Address', 'N/A')}")
    note = patient.get("Note") or patient.get("Notes") or patient.get("Problem", "")
    if note:
        lines.append(f"  নোট: {note}")
    therapist = patient.get("Therapist", "")
    if therapist:
        lines.append(f"  থেরাপিস্ট: {therapist}")
    lines.append("")

    package = sheets.get_active_package_for_patient(patient_id)
    if package:
        total = package.get("Total_Sessions", "N/A")
        done = package.get("Sessions_Completed", "N/A")
        lines.append(f"🗓️ সেশন: {done} সম্পন্ন / {total} মোট")
        lines.append("")

    payments = sheets.get_payments_for_patient(patient_id)
    if payments:
        lines.append("💳 পেমেন্ট হিস্টরি:")
        total_paid = 0.0
        last_due = 0.0
        for p in payments:
            date_str = p.get("Date", "")
            amount = float(p.get("Amount", 0) or 0)
            due = float(p.get("Due", 0) or 0)
            method = p.get("Payment_Method", "")
            total_paid += amount
            last_due = due
            lines.append(f"  • {date_str}: {amount:.0f} টাকা ({method})")
        lines.append("")
        lines.append(f"💰 সর্বমোট জমা: {total_paid:.0f} টাকা")
        lines.append(f"⏳ সর্বশেষ বাকি: {last_due:.0f} টাকা")
    else:
        lines.append("💳 কোনো পেমেন্ট রেকর্ড নেই।")
    lines.append("")

    appointments = sheets.get_appointments_for_patient(patient_id)
    if appointments:
        lines.append("📅 অ্যাপয়েন্টমেন্ট হিস্টরি:")
        for a in appointments[-10:]:
            date_str = a.get("Date", "")
            status = a.get("Status", "")
            lines.append(f"  • {date_str}: {status}")
    else:
        lines.append("📅 কোনো অ্যাপয়েন্টমেন্ট রেকর্ড নেই।")
    lines.append("")

    treatment_notes = sheets.get_treatment_notes_for_patient(patient_id)
    if treatment_notes:
        lines.append("📝 ট্রিটমেন্ট নোট:")
        for t in treatment_notes[-5:]:
            date_str = t.get("Date", "")
            note_text = t.get("Note", "") or t.get("Notes", "")
            lines.append(f"  • {date_str}: {note_text}")
    else:
        lines.append("📝 কোনো ট্রিটমেন্ট নোট নেই।")

    full_text = "\\n".join(lines)
    if len(full_text) > 4000:
        full_text = full_text[:3990] + "\\n...(আরও আছে)"

    await query.edit_message_text(full_text)''',
    new='''async def plist_action_hist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_hist_", "")

    full_text = _build_full_history_text(patient_id)
    if full_text is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return

    await query.edit_message_text(full_text, reply_markup=_patient_card_keyboard(patient_id))''',
    label="plist_action_hist: dedupe + attach Action Panel",
)

# ---------------------------------------------------------------------------
# 6) thist_date_callback — this was a dead-end screen (no buttons at all).
#    Attach the Action Panel using the Patient_ID already present on the note.
# ---------------------------------------------------------------------------
replace_once(
    old='''    await query.edit_message_text("\\n".join(lines))
    context.user_data.pop("thist_notes", None)
    return ConversationHandler.END''',
    new='''    patient_id = str(n.get("Patient_ID", "")).strip()
    context.user_data.pop("thist_notes", None)
    if patient_id:
        await query.edit_message_text("\\n".join(lines), reply_markup=_patient_card_keyboard(patient_id))
    else:
        await query.edit_message_text("\\n".join(lines))
    return ConversationHandler.END''',
    label="thist_date_callback: attach Action Panel (was a dead end)",
)

# ---------------------------------------------------------------------------
# 7) patient_list_back_callback — make "🔙 তালিকায় ফিরুন" work even when the
#    Action Panel was opened from Present/History/Treatment-History (i.e. the
#    patient list was never actually cached for this user yet).
# ---------------------------------------------------------------------------
replace_once(
    old='''async def patient_list_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = context.user_data.get("plist_last_page", 0)
    await _send_patient_list_page(query.message, context, page=page, edit=True)''',
    new='''async def patient_list_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not context.user_data.get("plist_patients"):
        # Action Panel অন্য ফ্লো (Present/History/Treatment History) থেকে এলে
        # plist_patients cache করা নাও থাকতে পারে — তখন এখানে বানিয়ে নেওয়া হয়,
        # যাতে "🔙 তালিকায় ফিরুন" কখনো খালি স্ক্রিন না দেখায়।
        patients = [
            p for p in sheets.get_all_patients()
            if str(p.get("Status", "")).strip() == "Active"
        ]
        patients.sort(key=lambda p: p.get("Full_Name", ""))
        context.user_data["plist_patients"] = {
            p.get("Patient_ID", "").strip(): p for p in patients
        }
    page = context.user_data.get("plist_last_page", 0)
    await _send_patient_list_page(query.message, context, page=page, edit=True)''',
    label="patient_list_back_callback: never dead-end on Back",
)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("\n🎉 Patch 1 applied successfully to bot.py")
print(f"   {len(original_src)} -> {len(src)} bytes")
