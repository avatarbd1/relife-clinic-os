#!/usr/bin/env python3
"""
Patch: Treatment Plan carry-over confirm + auto session number +
recent-patient quick-pick + multi-day/weekly-repeat appointment booking.
Run this once from ~/relife-clinic-os/03_Bot/
"""
import shutil

def main():
    shutil.copy("bot.py", "bot.py.before_treatmentplan_patch2")
    shutil.copy("sheets.py", "sheets.py.before_treatmentplan_patch2")
    print("🔒 Backup: bot.py.before_treatmentplan_patch2 / sheets.py.before_treatmentplan_patch2 তৈরি হলো\n")

    with open("sheets.py", "r", encoding="utf-8") as f:
        sh = f.read()

    old = '''def get_last_treatment_note_for_patient(patient_id: str) -> dict | None:
    """
    রোগীর সবচেয়ে সাম্প্রতিক ট্রিটমেন্ট নোট ফেরত দেয় (থাকলে), না থাকলে None।
    "গতকালের মতোই" রিপিট-এন্ট্রি ফিচারের জন্য ব্যবহৃত হয়।
    """
    notes = get_treatment_notes_for_patient(patient_id)
    if not notes:
        return None
    return notes[-1]'''
    new = '''def get_last_treatment_note_for_patient(patient_id: str) -> dict | None:
    """
    রোগীর সবচেয়ে সাম্প্রতিক ট্রিটমেন্ট নোট ফেরত দেয় (থাকলে), না থাকলে None।
    "গতকালের মতোই" রিপিট-এন্ট্রি ফিচারের জন্য ব্যবহৃত হয়।
    """
    notes = get_treatment_notes_for_patient(patient_id)
    if not notes:
        return None
    return notes[-1]


def get_recent_patients(limit: int = 6) -> list[dict]:
    """
    সাম্প্রতিক ট্রিটমেন্ট নোট থেকে সাম্প্রতিক রোগীদের তালিকা ফেরত দেয়
    (নতুন থেকে পুরনো, ডুপ্লিকেট ছাড়া) — Treatment Plan-এর শুরুতে quick-pick
    বাটন দেখানোর জন্য ব্যবহৃত হয়।
    """
    ws = _worksheet(config.SHEET_TREATMENTS)
    records = ws.get_all_records()
    seen = set()
    recent_ids = []
    for r in reversed(records):
        pid = str(r.get("Patient_ID", "")).strip()
        if pid and pid not in seen:
            seen.add(pid)
            recent_ids.append(pid)
        if len(recent_ids) >= limit:
            break
    by_id = {p.get("Patient_ID", "").strip(): p for p in get_all_patients()}
    return [by_id[pid] for pid in recent_ids if pid in by_id]


def get_next_session_number(patient_id: str) -> int:
    """রোগীর আগের ট্রিটমেন্ট নোট সংখ্যা গুনে পরবর্তী সেশন নম্বর অটো হিসাব করে।"""
    return len(get_treatment_notes_for_patient(patient_id)) + 1'''
    if sh.count(old) == 1:
        sh = sh.replace(old, new, 1)
        print("✅ sheets.py: get_recent_patients + get_next_session_number যোগ হলো")
    else:
        print(f"❌ sheets.py: anchor mismatch (found {sh.count(old)} বার) — SKIPPED")

    with open("sheets.py", "w", encoding="utf-8") as f:
        f.write(sh)

    with open("bot.py", "r", encoding="utf-8") as f:
        bt = f.read()

    edits = []

    edits.append(("state tuples: add APT_REPEAT + shift PAY/TREAT range", '''(
    REG_NAME,
    REG_PHONE,
    REG_PHONE_CONFIRM,
    REG_PHONE_DUP,
    REG_ADDRESS,
    REG_NOTE,
    REG_CONFIRM,
    APT_SEARCH,
    APT_SELECT,
    APT_DATE,
    APT_TIME,
    APT_THERAPIST,
    APT_CONFIRM,
) = range(13)

(
    PAY_SEARCH,
    PAY_SELECT,
    PAY_SESSION,
    PAY_AMOUNT,
    PAY_METHOD,
    PAY_CONFIRM,
) = range(13, 19)

(
    TREAT_SEARCH,
    TREAT_SELECT,
    TREAT_DIAGNOSIS,
    TREAT_GIVEN,
    TREAT_EXERCISE,
    TREAT_ELECTRO,
    TREAT_MANUAL,
    TREAT_SESSION,
    TREAT_NEXTVISIT,
    TREAT_CONFIRM,
) = range(19, 29)''', '''(
    REG_NAME,
    REG_PHONE,
    REG_PHONE_CONFIRM,
    REG_PHONE_DUP,
    REG_ADDRESS,
    REG_NOTE,
    REG_CONFIRM,
    APT_SEARCH,
    APT_SELECT,
    APT_DATE,
    APT_REPEAT,
    APT_TIME,
    APT_THERAPIST,
    APT_CONFIRM,
) = range(14)

(
    PAY_SEARCH,
    PAY_SELECT,
    PAY_SESSION,
    PAY_AMOUNT,
    PAY_METHOD,
    PAY_CONFIRM,
) = range(14, 20)

(
    TREAT_SEARCH,
    TREAT_SELECT,
    TREAT_DIAGNOSIS,
    TREAT_GIVEN,
    TREAT_EXERCISE,
    TREAT_ELECTRO,
    TREAT_MANUAL,
    TREAT_SESSION,
    TREAT_NEXTVISIT,
    TREAT_CONFIRM,
) = range(20, 30)'''))

    edits.append(("TPLAN state tuple: add TPLAN_CARRYOVER", '''(
    TPLAN_SEARCH,
    TPLAN_SELECT,
    TPLAN_DIAGNOSIS,
    TPLAN_GIVEN,
    TPLAN_EXERCISE,
    TPLAN_ELECTRO,
    TPLAN_MANUAL,
    TPLAN_MACHINES,
) = range(29, 37)''', '''(
    TPLAN_SEARCH,
    TPLAN_SELECT,
    TPLAN_CARRYOVER,
    TPLAN_DIAGNOSIS,
    TPLAN_GIVEN,
    TPLAN_EXERCISE,
    TPLAN_ELECTRO,
    TPLAN_MANUAL,
    TPLAN_MACHINES,
) = range(30, 39)'''))

    edits.append(("add _date_multi_keyboard + _repeat_keyboard helpers", '''def _date_keyboard() -> InlineKeyboardMarkup:
    today = datetime.now()
    buttons = []
    row = []
    for i in range(7):
        d = today + timedelta(days=i)
        label = d.strftime("%d %b") + f" ({BN_WEEKDAYS[d.weekday()]})"
        row.append(InlineKeyboardButton(label, callback_data=f"aptdate_{d.strftime('%Y-%m-%d')}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)''', '''def _date_keyboard() -> InlineKeyboardMarkup:
    today = datetime.now()
    buttons = []
    row = []
    for i in range(7):
        d = today + timedelta(days=i)
        label = d.strftime("%d %b") + f" ({BN_WEEKDAYS[d.weekday()]})"
        row.append(InlineKeyboardButton(label, callback_data=f"aptdate_{d.strftime('%Y-%m-%d')}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _date_multi_keyboard(selected: set) -> InlineKeyboardMarkup:
    """২ সপ্তাহের ক্যালেন্ডার, একাধিক দিন টগল করে বাছাই করা যায়।"""
    today = datetime.now()
    buttons = []
    row = []
    for i in range(14):
        d = today + timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")
        prefix = "✅ " if date_str in selected else "⬜ "
        label = prefix + d.strftime("%d %b") + f" ({BN_WEEKDAYS[d.weekday()]})"
        row.append(InlineKeyboardButton(label, callback_data=f"aptdate_{date_str}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    done_label = f"✅ সম্পন্ন ({len(selected)} দিন বাছাই করা হয়েছে)" if selected else "✅ সম্পন্ন"
    buttons.append([InlineKeyboardButton(done_label, callback_data="aptdatedone_")])
    return InlineKeyboardMarkup(buttons)


def _repeat_keyboard() -> InlineKeyboardMarkup:
    """বাছাই করা দিনগুলো প্রতি সপ্তাহে repeat করার অপশন।"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("শুধু এই দিনগুলো", callback_data="aptrepeat_0")],
        [
            InlineKeyboardButton("🔁 +১ সপ্তাহ", callback_data="aptrepeat_1"),
            InlineKeyboardButton("🔁 +২ সপ্তাহ", callback_data="aptrepeat_2"),
        ],
        [InlineKeyboardButton("🔁 +৩ সপ্তাহ", callback_data="aptrepeat_3")],
    ])'''))

    edits.append(("apt_select: send multi-date keyboard", '''    context.user_data["new_appointment"]["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["new_appointment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["new_appointment"]["Department"] = patient.get("Department", "")
    context.user_data.pop("apt_search_results", None)
    await update.message.reply_text(
        f"রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\\n\\n"
        "তারিখ বেছে নাও (অথবা টাইপ করো, উদাহরণ: 2026-07-15):",
        reply_markup=_date_keyboard(),
    )
    return APT_DATE''', '''    context.user_data["new_appointment"]["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["new_appointment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["new_appointment"]["Department"] = patient.get("Department", "")
    context.user_data.pop("apt_search_results", None)
    context.user_data["apt_selected_dates"] = set()
    await update.message.reply_text(
        f"রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\\n\\n"
        "একাধিক দিন বেছে নিতে পারো — প্রতিটাতে ট্যাপ করো, শেষে ✅ সম্পন্ন চাপো "
        "(অথবা একটা তারিখ টাইপ করো, উদাহরণ: 2026-07-15):",
        reply_markup=_date_multi_keyboard(set()),
    )
    return APT_DATE'''))

    edits.append(("apt date handlers: toggle + done + weekly-repeat + typed fallback", '''async def apt_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.replace("aptdate_", "")
    context.user_data.setdefault("new_appointment", {})["Date"] = date_str
    await query.edit_message_text(f"✅ তারিখ নির্বাচন করা হয়েছে: {date_str}")
    await query.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো):", reply_markup=_time_keyboard()
    )
    return APT_TIME


async def apt_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Date"] = update.message.text.strip()
    await update.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো):", reply_markup=_time_keyboard()
    )
    return APT_TIME''', '''async def apt_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.replace("aptdate_", "")
    selected = context.user_data.setdefault("apt_selected_dates", set())
    if date_str in selected:
        selected.discard(date_str)
    else:
        selected.add(date_str)
    await query.edit_message_reply_markup(reply_markup=_date_multi_keyboard(selected))
    return APT_DATE


async def apt_date_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected = context.user_data.get("apt_selected_dates", set())
    if not selected:
        await query.answer("কমপক্ষে ১টা দিন বাছাই করো।", show_alert=True)
        return APT_DATE
    await query.answer()
    await query.edit_message_text(f"✅ {len(selected)}টি দিন বাছাই করা হয়েছে।")
    await query.message.reply_text(
        "এই দিনগুলো কি প্রতি সপ্তাহে repeat হবে?", reply_markup=_repeat_keyboard()
    )
    return APT_REPEAT


async def apt_repeat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    weeks = int(query.data.replace("aptrepeat_", ""))
    base_dates = context.user_data.get("apt_selected_dates", set())
    all_dates = set(base_dates)
    for base in base_dates:
        base_dt = datetime.strptime(base, "%Y-%m-%d")
        for w in range(1, weeks + 1):
            all_dates.add((base_dt + timedelta(weeks=w)).strftime("%Y-%m-%d"))
    dates_sorted = sorted(all_dates)
    context.user_data.setdefault("new_appointment", {})["Dates"] = dates_sorted
    await query.edit_message_text(f"✅ মোট {len(dates_sorted)}টি তারিখ বাছাই হলো।")
    await query.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো):", reply_markup=_time_keyboard()
    )
    return APT_TIME


async def apt_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date_str = update.message.text.strip()
    selected = context.user_data.setdefault("apt_selected_dates", set())
    selected.add(date_str)
    await update.message.reply_text(
        f"✅ {date_str} যোগ হলো। আরও দিন বাছাই করতে পারো, শেষে ✅ সম্পন্ন চাপো:",
        reply_markup=_date_multi_keyboard(selected),
    )
    return APT_DATE'''))

    edits.append(("apt_therapist(_callback): multi-date summary", '''async def apt_therapist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Therapist"] = update.message.text.strip()
    a = context.user_data["new_appointment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\\n\\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\\n"
        f"Department: {a['Department']}\\n"
        f"তারিখ: {a['Date']}\\nসময়: {a['Time']}\\n"
        f"থেরাপিস্ট: {a['Therapist']}\\n\\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return APT_CONFIRM


async def apt_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    therapist_name = query.data.replace("aptther_", "")
    context.user_data["new_appointment"]["Therapist"] = therapist_name
    a = context.user_data["new_appointment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\\n\\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\\n"
        f"Department: {a['Department']}\\n"
        f"তারিখ: {a['Date']}\\nসময়: {a['Time']}\\n"
        f"থেরাপিস্ট: {a['Therapist']}\\n\\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await query.edit_message_text(f"✅ থেরাপিস্ট নির্বাচন করা হয়েছে: {therapist_name}")
    await query.message.reply_text(summary, reply_markup=confirm_keyboard)
    return APT_CONFIRM''', '''def _apt_summary_text(a: dict) -> str:
    dates = a.get("Dates") or [a.get("Date", "")]
    dates_line = f"তারিখ ({len(dates)}টি): " + ", ".join(dates)
    return (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\\n\\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\\n"
        f"Department: {a['Department']}\\n"
        f"{dates_line}\\nসময়: {a['Time']}\\n"
        f"থেরাপিস্ট: {a['Therapist']}\\n\\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )


async def apt_therapist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Therapist"] = update.message.text.strip()
    a = context.user_data["new_appointment"]
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(_apt_summary_text(a), reply_markup=confirm_keyboard)
    return APT_CONFIRM


async def apt_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    therapist_name = query.data.replace("aptther_", "")
    context.user_data["new_appointment"]["Therapist"] = therapist_name
    a = context.user_data["new_appointment"]
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await query.edit_message_text(f"✅ থেরাপিস্ট নির্বাচন করা হয়েছে: {therapist_name}")
    await query.message.reply_text(_apt_summary_text(a), reply_markup=confirm_keyboard)
    return APT_CONFIRM'''))

    edits.append(("apt_confirm: create one appointment per selected date", '''async def apt_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        appointment_id = sheets.add_appointment(
            context.user_data["new_appointment"],
            created_by=staff.get("Full_Name", "Unknown"),
        )
        await update.message.reply_text(
            f"✅ অ্যাপয়েন্টমেন্ট বুক হয়েছে! Appointment ID: {appointment_id}",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    else:
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("new_appointment", None)
    return ConversationHandler.END


async def apt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_search_results", None)
    await update.effective_message.reply_text(
        "অ্যাপয়েন্টমেন্ট বুকিং বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END''', '''async def apt_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        a = context.user_data["new_appointment"]
        dates = a.get("Dates") or [a.get("Date", "")]
        created_ids = []
        for d in dates:
            per_date = dict(a)
            per_date["Date"] = d
            appointment_id = sheets.add_appointment(
                per_date, created_by=staff.get("Full_Name", "Unknown"),
            )
            created_ids.append(appointment_id)
        if len(created_ids) == 1:
            await update.message.reply_text(
                f"✅ অ্যাপয়েন্টমেন্ট বুক হয়েছে! Appointment ID: {created_ids[0]}",
                reply_markup=_menu_keyboard(staff.get("Role", "")),
            )
        else:
            await update.message.reply_text(
                f"✅ {len(created_ids)}টি অ্যাপয়েন্টমেন্ট বুক হয়েছে!\\n"
                f"IDs: {', '.join(created_ids)}",
                reply_markup=_menu_keyboard(staff.get("Role", "")),
            )
    else:
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_selected_dates", None)
    return ConversationHandler.END


async def apt_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_appointment", None)
    context.user_data.pop("apt_search_results", None)
    context.user_data.pop("apt_selected_dates", None)
    await update.effective_message.reply_text(
        "অ্যাপয়েন্টমেন্ট বুকিং বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END'''))

    edits.append(("tplan_start: recent-patient quick-pick buttons", '''    context.user_data["tplan"] = {}
    context.user_data["tplan_selected"] = set()
    await update.message.reply_text(
        "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TPLAN_SEARCH''', '''    context.user_data["tplan"] = {}
    context.user_data["tplan_selected"] = set()
    recent = sheets.get_recent_patients(limit=6)
    if recent:
        context.user_data["tplan_search_results"] = {
            p.get("Patient_ID", "").strip(): p for p in recent
        }
        buttons = [
            [InlineKeyboardButton(
                f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
                callback_data=f"tplansel_{p.get('Patient_ID')}",
            )]
            for p in recent
        ]
        await update.message.reply_text(
            "সাম্প্রতিক রোগী থেকে বেছে নাও, অথবা নাম/ফোন/আইডি টাইপ করো (খুঁজতে):",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        await update.message.reply_text(
            "রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):",
            reply_markup=ReplyKeyboardRemove(),
        )
    return TPLAN_SEARCH'''))

    edits.append(("tplan_select_callback: carry-over summary + one-button confirm", '''    last = sheets.get_last_treatment_note_for_patient(patient_id)
    if last:
        t = context.user_data["tplan"]
        t["Diagnosis"] = last.get("Diagnosis", "")
        t["Treatment_Given"] = last.get("Treatment_Given", "")
        t["Exercise"] = last.get("Exercise", "")
        t["Electrotherapy"] = last.get("Electrotherapy", "")
        t["Manual_Therapy"] = last.get("Manual_Therapy", "")
        prev_machines = [m.strip() for m in str(last.get("Machines", "")).split(",") if m.strip()]
        selected = {idx for idx, name in enumerate(MACHINE_LIST) if name in prev_machines}
        context.user_data["tplan_selected"] = selected
        await query.edit_message_text(
            f"✅ {patient.get('Full_Name')} ({patient_id}) — আগের ভিজিট থেকে অটো-ক্যারি-ওভার হয়েছে।"
        )
        await query.message.reply_text(
            "আজকের মেশিন/মোডালিটি বেছে নাও, তারপর সম্পন্ন চাপো:",
            reply_markup=_machine_keyboard(selected),
        )
        return TPLAN_MACHINES''', '''    last = sheets.get_last_treatment_note_for_patient(patient_id)
    if last:
        t = context.user_data["tplan"]
        t["Diagnosis"] = last.get("Diagnosis", "")
        t["Treatment_Given"] = last.get("Treatment_Given", "")
        t["Exercise"] = last.get("Exercise", "")
        t["Electrotherapy"] = last.get("Electrotherapy", "")
        t["Manual_Therapy"] = last.get("Manual_Therapy", "")
        prev_machines = [m.strip() for m in str(last.get("Machines", "")).split(",") if m.strip()]
        selected = {idx for idx, name in enumerate(MACHINE_LIST) if name in prev_machines}
        context.user_data["tplan_selected"] = selected
        machines_line = ", ".join(MACHINE_LIST[i] for i in sorted(selected)) or "(কিছু নেই)"
        summary = (
            f"রোগী: {patient.get('Full_Name')} ({patient_id})\\n\\n"
            "আগের ভিজিট থেকে অটো-ক্যারি-ওভার হয়েছে:\\n"
            f"সমস্যা: {t['Diagnosis'] or '-'}\\n"
            f"ট্রিটমেন্ট: {t['Treatment_Given'] or '-'}\\n"
            f"এক্সারসাইজ: {t['Exercise'] or '-'}\\n"
            f"ইলেক্ট্রোথেরাপি: {t['Electrotherapy'] or '-'}\\n"
            f"ম্যানুয়াল থেরাপি: {t['Manual_Therapy'] or '-'}\\n"
            f"মেশিন: {machines_line}"
        )
        carry_buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ গতকালের মতোই — সেভ করো", callback_data="tpcarry_same")],
            [InlineKeyboardButton("✏️ মেশিন পরিবর্তন করবো", callback_data="tpcarry_edit")],
        ])
        await query.edit_message_text(summary, reply_markup=carry_buttons)
        return TPLAN_CARRYOVER'''))

    edits.append(("tplan_done: extract shared save helper + session auto-calc + tplan_carryover_callback", '''async def tplan_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    t = context.user_data.get("tplan", {})
    selected = context.user_data.get("tplan_selected", set())
    t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
    try:
        treatment_id = sheets.add_treatment_note(t, created_by=staff.get("Full_Name", "Unknown"))
        await query.edit_message_text(
            f"✅ ট্রিটমেন্ট প্ল্যান সেভ হয়েছে! ID: {treatment_id}\\n"
            f"মেশিন: {t['Machines'] or '(কিছু বাছাই করা হয়নি)'}"
        )
    except Exception as e:
        logger.exception("tplan_done ব্যর্থ হয়েছে")
        await query.edit_message_text(f"❌ সেভ করতে সমস্যা হয়েছে।\\nError: {e}")
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_selected", None)
    await query.message.reply_text(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff.get("Role", ""))
    )
    return ConversationHandler.END''', '''async def _tplan_save_and_reply(query, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    t = context.user_data.get("tplan", {})
    selected = context.user_data.get("tplan_selected", set())
    t["Machines"] = ", ".join(MACHINE_LIST[i] for i in sorted(selected))
    try:
        t["Session_No"] = sheets.get_next_session_number(t.get("Patient_ID", ""))
        treatment_id = sheets.add_treatment_note(t, created_by=staff.get("Full_Name", "Unknown"))
        await query.edit_message_text(
            f"✅ ট্রিটমেন্ট প্ল্যান সেভ হয়েছে! ID: {treatment_id}\\n"
            f"সেশন নম্বর: {t['Session_No']} (অটো)\\n"
            f"মেশিন: {t['Machines'] or '(কিছু বাছাই করা হয়নি)'}"
        )
    except Exception as e:
        logger.exception("tplan সেভ ব্যর্থ হয়েছে")
        await query.edit_message_text(f"❌ সেভ করতে সমস্যা হয়েছে।\\nError: {e}")
    context.user_data.pop("tplan", None)
    context.user_data.pop("tplan_selected", None)
    await query.message.reply_text(
        "নিচের মেনু থেকে বেছে নাও 👇", reply_markup=_menu_keyboard(staff.get("Role", ""))
    )


async def tplan_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await _tplan_save_and_reply(query, context)
    return ConversationHandler.END


async def tplan_carryover_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.replace("tpcarry_", "")
    if action == "same":
        await _tplan_save_and_reply(query, context)
        return ConversationHandler.END
    selected = context.user_data.get("tplan_selected", set())
    await query.edit_message_text("আজকের মেশিন/মোডালিটি বেছে নাও, তারপর সম্পন্ন চাপো:")
    await query.message.reply_text(
        "মেশিন বেছে নাও:", reply_markup=_machine_keyboard(selected)
    )
    return TPLAN_MACHINES'''))

    edits.append(("main(): wire apt date/repeat callback handlers", '''            APT_DATE: [
                CallbackQueryHandler(apt_date_callback, pattern="^aptdate_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_date),
            ],
            APT_TIME: [''', '''            APT_DATE: [
                CallbackQueryHandler(apt_date_done_callback, pattern="^aptdatedone_"),
                CallbackQueryHandler(apt_date_callback, pattern="^aptdate_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_date),
            ],
            APT_REPEAT: [
                CallbackQueryHandler(apt_repeat_callback, pattern="^aptrepeat_"),
            ],
            APT_TIME: ['''))

    edits.append(("main(): wire tplan quick-pick + carryover state", '''            TPLAN_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_search)],
            TPLAN_SELECT: [CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_")],
            TPLAN_DIAGNOSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_diagnosis)],''', '''            TPLAN_SEARCH: [
                CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_search),
            ],
            TPLAN_SELECT: [CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_")],
            TPLAN_CARRYOVER: [CallbackQueryHandler(tplan_carryover_callback, pattern="^tpcarry_")],
            TPLAN_DIAGNOSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_diagnosis)],'''))

    edits.append(("plist_action_apt: use multi-date keyboard too", '''    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text(
        "তারিখ বেছে নাও (অথবা টাইপ করো, উদাহরণ: 2026-07-15):",
        reply_markup=_date_keyboard(),
    )
    return APT_DATE''', '''    context.user_data["apt_selected_dates"] = set()
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text(
        "একাধিক দিন বেছে নিতে পারো — প্রতিটাতে ট্যাপ করো, শেষে ✅ সম্পন্ন চাপো "
        "(অথবা একটা তারিখ টাইপ করো, উদাহরণ: 2026-07-15):",
        reply_markup=_date_multi_keyboard(set()),
    )
    return APT_DATE'''))

    ok_count = 0
    for label, old, new in edits:
        count = bt.count(old)
        if count != 1:
            print(f"❌ {label}: expected 1 match, found {count} — SKIPPED (file may already differ)")
            continue
        bt = bt.replace(old, new, 1)
        print(f"✅ {label}")
        ok_count += 1

    with open("bot.py", "w", encoding="utf-8") as f:
        f.write(bt)

    print(f"\n{ok_count}/{len(edits)} bot.py এডিট প্রয়োগ হলো।\n")

    import ast
    try:
        ast.parse(open("bot.py", encoding="utf-8").read())
        ast.parse(open("sheets.py", encoding="utf-8").read())
        print("✅ bot.py ও sheets.py — সিনট্যাক্স ঠিক আছে (ast parse pass)")
    except SyntaxError as e:
        print(f"❌ সিনট্যাক্স এরর: {e}")
        print("‼️ bot.py.before_treatmentplan_patch2 থেকে রিস্টোর করার কথা ভাবো।")


if __name__ == "__main__":
    main()
