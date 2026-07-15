"""
patch_patient_list.py
রোগীর তালিকা (Patient List) ফিচার যোগ করার প্যাচ স্ক্রিপ্ট।
03_Bot/ ফোল্ডারে রেখে চালাও: python patch_patient_list.py
আগে backup নিয়ে নেবে (স্ক্রিপ্ট নিজেই backup বানায়)।
"""

import shutil
import sys

ROLES_FILE = "roles.py"
BOT_FILE = "bot.py"


def backup(path):
    bak = path + ".bak"
    shutil.copy(path, bak)
    print(f"✅ Backup নেওয়া হলো: {bak}")


def apply_replace(content, old, new, label):
    count = content.count(old)
    if count != 1:
        print(f"❌ ব্যর্থ: '{label}' — {count} বার মিলেছে (দরকার ছিল ঠিক ১ বার)।")
        print("   হয়তো ফাইলটা আগেই পরিবর্তিত, অথবা কোড ভিন্ন। ম্যানুয়ালি চেক করো।")
        sys.exit(1)
    print(f"✅ প্রয়োগ হলো: {label}")
    return content.replace(old, new)


with open(ROLES_FILE, "r", encoding="utf-8") as f:
    roles_content = f.read()

backup(ROLES_FILE)

roles_content = apply_replace(
    roles_content,
    'MENU_PATIENT_HISTORY = "📜 রোগীর ইতিহাস"',
    'MENU_PATIENT_HISTORY = "📜 রোগীর ইতিহাস"\n'
    'MENU_PATIENT_LIST = "📋 রোগীর তালিকা"',
    "MENU_PATIENT_LIST কনস্ট্যান্ট যোগ",
)

roles_content = apply_replace(
    roles_content,
    "    Role.OWNER: [\n"
    "        [MENU_HOME],\n"
    "        [MENU_PATIENT_REG, MENU_PATIENT_HISTORY],\n",
    "    Role.OWNER: [\n"
    "        [MENU_HOME],\n"
    "        [MENU_PATIENT_REG, MENU_PATIENT_HISTORY],\n"
    "        [MENU_PATIENT_LIST],\n",
    "Owner মেনুতে রোগীর তালিকা যোগ",
)

roles_content = apply_replace(
    roles_content,
    "    Role.RECEPTIONIST: [\n"
    "        [MENU_HOME],\n"
    "        [MENU_PATIENT_REG],\n",
    "    Role.RECEPTIONIST: [\n"
    "        [MENU_HOME],\n"
    "        [MENU_PATIENT_REG],\n"
    "        [MENU_PATIENT_LIST],\n",
    "Receptionist মেনুতে রোগীর তালিকা যোগ",
)

roles_content = apply_replace(
    roles_content,
    "    Role.MANAGER: [\n"
    "        [MENU_HOME],\n"
    "        [MENU_PATIENT_REG],\n",
    "    Role.MANAGER: [\n"
    "        [MENU_HOME],\n"
    "        [MENU_PATIENT_REG],\n"
    "        [MENU_PATIENT_LIST],\n",
    "Manager মেনুতে রোগীর তালিকা যোগ",
)

with open(ROLES_FILE, "w", encoding="utf-8") as f:
    f.write(roles_content)

print(f"✅ {ROLES_FILE} সেভ হয়েছে।\n")


with open(BOT_FILE, "r", encoding="utf-8") as f:
    bot_content = f.read()

backup(BOT_FILE)

bot_content = apply_replace(
    bot_content,
    "    roles.MENU_PATIENT_HISTORY,\n]",
    "    roles.MENU_PATIENT_HISTORY,\n"
    "    roles.MENU_PATIENT_LIST,\n]",
    "_ALL_MENU_ITEMS-এ MENU_PATIENT_LIST যোগ",
)

NEW_FUNCTIONS = '''
def _patient_card_text(patient: dict) -> str:
    name = patient.get("Full_Name", "")
    pid = patient.get("Patient_ID", "")
    phone = patient.get("Phone", "")
    dept = patient.get("Department", "")
    therapist = patient.get("Therapist", "")
    total_bill = patient.get("Total_Bill", 0) or 0
    paid = patient.get("Paid_Amount", 0) or 0
    due = patient.get("Due_Amount", 0) or 0
    return (
        f"👤 {name} ({pid})\\n"
        f"📞 {phone}\\n"
        f"🏥 বিভাগ: {dept}\\n"
        f"🧑‍⚕️ থেরাপিস্ট: {therapist or '—'}\\n\\n"
        f"💰 মোট বিল: {total_bill}\\n"
        f"✅ জমা হয়েছে: {paid}\\n"
        f"⏳ বাকি: {due}"
    )


def _patient_card_keyboard(patient_id: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("💰 পেমেন্ট নিন", callback_data=f"plistact_pay_{patient_id}"),
            InlineKeyboardButton("📅 অ্যাপয়েন্টমেন্ট", callback_data=f"plistact_apt_{patient_id}"),
        ],
        [
            InlineKeyboardButton("📝 ট্রিটমেন্ট নোট", callback_data=f"plistact_treat_{patient_id}"),
            InlineKeyboardButton("📜 সম্পূর্ণ ইতিহাস", callback_data=f"plistact_hist_{patient_id}"),
        ],
        [InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data="plistact_back")],
    ]
    return InlineKeyboardMarkup(buttons)


async def patient_list_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_PATIENT_LIST):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    patients = [
        p for p in sheets.get_all_patients()
        if str(p.get("Status", "")).strip() == "Active"
    ]
    patients.sort(key=lambda p: p.get("Full_Name", ""))
    if not patients:
        await update.message.reply_text("কোনো সক্রিয় রোগী পাওয়া যায়নি।")
        return
    context.user_data["plist_patients"] = {
        p.get("Patient_ID", "").strip(): p for p in patients
    }
    await _send_patient_list_page(update.message, context, page=0)


async def _send_patient_list_page(message, context: ContextTypes.DEFAULT_TYPE, page: int, edit: bool = False):
    patients = list(context.user_data.get("plist_patients", {}).values())
    per_page = 8
    start = page * per_page
    chunk = patients[start:start + per_page]
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"plistsel_{p.get('Patient_ID')}_{page}",
        )]
        for p in chunk
    ]
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ আগের", callback_data=f"plistpage_{page - 1}"))
    if start + per_page < len(patients):
        nav.append(InlineKeyboardButton("পরের ➡️", callback_data=f"plistpage_{page + 1}"))
    if nav:
        buttons.append(nav)
    text = f"📋 রোগীর তালিকা (পাতা {page + 1}) — নাম চাপো:"
    markup = InlineKeyboardMarkup(buttons)
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.reply_text(text, reply_markup=markup)


async def patient_list_page_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = int(query.data.replace("plistpage_", ""))
    await _send_patient_list_page(query.message, context, page=page, edit=True)


async def patient_list_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, patient_id, page = query.data.split("_", 2)
    patients = context.user_data.get("plist_patients", {})
    patient = patients.get(patient_id)
    if not patient:
        await query.edit_message_text("❌ তালিকার মেয়াদ শেষ। আবার 📋 রোগীর তালিকা চাপো।")
        return
    context.user_data["plist_last_page"] = int(page)
    await query.edit_message_text(
        _patient_card_text(patient),
        reply_markup=_patient_card_keyboard(patient_id),
    )


async def patient_list_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = context.user_data.get("plist_last_page", 0)
    await _send_patient_list_page(query.message, context, page=page, edit=True)


async def plist_action_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_pay_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["payment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
    }
    total_bill = patient.get("Total_Bill", 0) or 0
    paid_amount = patient.get("Paid_Amount", 0) or 0
    due_amount = patient.get("Due_Amount", 0) or 0
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\\n\\n"
        f"মোট বিল: {total_bill}\\nজমা হয়েছে: {paid_amount}\\nবাকি: {due_amount}"
    )
    await query.message.reply_text(
        "আজ কয়টা সেশন হলো লেখো (না থাকলে 0):",
        reply_markup=_number_keyboard([str(n) for n in range(0, 6)]),
    )
    return PAY_SESSION


async def plist_action_apt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_apt_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["new_appointment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
    }
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text(
        "তারিখ বেছে নাও (অথবা টাইপ করো, উদাহরণ: 2026-07-15):",
        reply_markup=_date_keyboard(),
    )
    return APT_DATE


async def plist_action_treat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_treat_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["treatment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
    }
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text("আজকের সমস্যা/পর্যবেক্ষণ (Diagnosis) লেখো:")
    return TREAT_DIAGNOSIS


async def plist_action_hist(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    await query.edit_message_text(full_text)


def main():'''

bot_content = apply_replace(
    bot_content,
    "\ndef main():",
    NEW_FUNCTIONS,
    "নতুন প্যাশেন্ট-লিস্ট ফাংশনগুলো main()-এর আগে বসানো",
)

bot_content = apply_replace(
    bot_content,
    '    app.add_handler(CallbackQueryHandler(apt_status_callback, pattern="^aptstatus_"))\n',
    '    app.add_handler(CallbackQueryHandler(apt_status_callback, pattern="^aptstatus_"))\n'
    "\n"
    "    app.add_handler(\n"
    '        MessageHandler(filters.Regex(f"^{roles.MENU_PATIENT_LIST}$"), patient_list_start)\n'
    "    )\n"
    '    app.add_handler(CallbackQueryHandler(patient_list_page_callback, pattern="^plistpage_"))\n'
    '    app.add_handler(CallbackQueryHandler(patient_list_select_callback, pattern="^plistsel_"))\n'
    '    app.add_handler(CallbackQueryHandler(patient_list_back_callback, pattern="^plistact_back$"))\n'
    '    app.add_handler(CallbackQueryHandler(plist_action_hist, pattern="^plistact_hist_"))\n',
    "patient list মেনু ও callback হ্যান্ডলার রেজিস্ট্রেশন",
)

bot_content = apply_replace(
    bot_content,
    "    pay_conv = ConversationHandler(\n"
    "        entry_points=[\n"
    '            MessageHandler(filters.Regex(f"^{roles.MENU_PAYMENT}$"), pay_start)\n'
    "        ],\n",
    "    pay_conv = ConversationHandler(\n"
    "        entry_points=[\n"
    '            MessageHandler(filters.Regex(f"^{roles.MENU_PAYMENT}$"), pay_start),\n'
    '            CallbackQueryHandler(plist_action_pay, pattern="^plistact_pay_"),\n'
    "        ],\n",
    "pay_conv-এ plist entry point যোগ",
)

bot_content = apply_replace(
    bot_content,
    "    apt_conv = ConversationHandler(\n"
    "        entry_points=[\n"
    '            MessageHandler(filters.Regex(f"^{roles.MENU_APPOINTMENT}$"), apt_start)\n'
    "        ],\n",
    "    apt_conv = ConversationHandler(\n"
    "        entry_points=[\n"
    '            MessageHandler(filters.Regex(f"^{roles.MENU_APPOINTMENT}$"), apt_start),\n'
    '            CallbackQueryHandler(plist_action_apt, pattern="^plistact_apt_"),\n'
    "        ],\n",
    "apt_conv-এ plist entry point যোগ",
)

bot_content = apply_replace(
    bot_content,
    "    treat_conv = ConversationHandler(\n"
    "        entry_points=[\n"
    '            MessageHandler(filters.Regex(f"^{roles.MENU_TREATMENT_NOTE}$"), treat_start)\n'
    "        ],\n",
    "    treat_conv = ConversationHandler(\n"
    "        entry_points=[\n"
    '            MessageHandler(filters.Regex(f"^{roles.MENU_TREATMENT_NOTE}$"), treat_start),\n'
    '            CallbackQueryHandler(plist_action_treat, pattern="^plistact_treat_"),\n'
    "        ],\n",
    "treat_conv-এ plist entry point যোগ",
)

with open(BOT_FILE, "w", encoding="utf-8") as f:
    f.write(bot_content)

print(f"✅ {BOT_FILE} সেভ হয়েছে।\n")
print("🎉 প্যাচ সম্পূর্ণ! এখন 'python3 -m py_compile bot.py roles.py' দিয়ে সিনট্যাক্স চেক করো।")
