import re

PATH = "bot.py"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()


def replace_once(src, old, new, label):
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"❌ FAILED at '{label}': found {count} matches (need exactly 1)")
    return src.replace(old, new, 1)


old = 'REG_PHOTO_CHOICE, REG_PHOTO_WAIT, REG_PHOTO_CONFIRM = range(90, 93)'
new = 'REG_PHOTO_CHOICE, REG_PHOTO_WAIT, REG_PHOTO_CONFIRM, REG_MISSING = range(90, 94)'
src = replace_once(src, old, new, "add REG_MISSING state")

old = '''async def _reg_ask_address_or_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = context.user_data.get("new_patient", {})
    if not p.get("Address"):
        await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
        return REG_ADDRESS
    await update.message.reply_text(
        "সমস্যা/বয়স/অন্য কিছু থাকলে এক লাইনে লেখো (না থাকলে - দাও):",
        reply_markup=_skip_keyboard(),
    )
    return REG_NOTE


async def _reg_resume_after_prefill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = context.user_data.setdefault("new_patient", {})
    if not p.get("Full_Name"):
        await update.message.reply_text(
            "নতুন রোগীর পূর্ণ নাম লেখো:", reply_markup=ReplyKeyboardRemove()
        )
        return REG_NAME
    if not p.get("Phone"):
        await update.message.reply_text(
            "ফোন নম্বর লেখো:", reply_markup=ReplyKeyboardRemove()
        )
        return REG_PHONE
    existing = sheets.find_patient_by_phone(p["Phone"])
    if existing:
        dup_keyboard = ReplyKeyboardMarkup(
            [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "⚠️ এই ফোন নম্বরে ইতিমধ্যে রোগী আছে:\n"
            f"নাম: {existing.get('Full_Name')}\n"
            f"Patient ID: {existing.get('Patient_ID')}\n\n"
            "তবুও কি নতুন করে রেজিস্ট্রেশন করবে?",
            reply_markup=dup_keyboard,
        )
        return REG_PHONE_DUP
    if not p.get("Address"):
        await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
        return REG_ADDRESS
    await update.message.reply_text(
        "সমস্যা/বয়স/অন্য কিছু থাকলে এক লাইনে লেখো (না থাকলে - দাও):",
        reply_markup=_skip_keyboard(),
    )
    return REG_NOTE'''

new = '''REG_REQUIRED_FIELDS = [
    ("Full_Name", "নাম"),
    ("Phone", "ফোন নম্বর"),
    ("Address", "ঠিকানা"),
    ("Age", "বয়স"),
]
REG_FIELD_EXAMPLES = {
    "Full_Name": "রহিম উদ্দিন",
    "Phone": "01712345678",
    "Address": "ঢাকা",
    "Age": "৩৫",
}


def _reg_missing_fields(p: dict):
    return [(k, label) for k, label in REG_REQUIRED_FIELDS if not str(p.get(k, "")).strip()]


async def _reg_collect_missing_or_continue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = context.user_data.setdefault("new_patient", {})
    missing = _reg_missing_fields(p)
    if missing:
        context.user_data["reg_missing_fields"] = [k for k, _ in missing]
        labels = ", ".join(label for _, label in missing)
        example = ", ".join(REG_FIELD_EXAMPLES[k] for k, _ in missing)
        await update.message.reply_text(
            f"এই তথ্যগুলো একলাইনে লেখো: {labels}\n\nযেমন: {example}",
            reply_markup=ReplyKeyboardRemove(),
        )
        return REG_MISSING
    return await _reg_after_fields_complete(update, context)


async def _reg_after_fields_complete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = context.user_data.get("new_patient", {})
    phone = str(p.get("Phone", "")).strip()
    if phone and not context.user_data.get("reg_dup_checked"):
        existing = sheets.find_patient_by_phone(phone)
        if existing:
            context.user_data["reg_dup_checked"] = True
            dup_keyboard = ReplyKeyboardMarkup(
                [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
            )
            await update.message.reply_text(
                "⚠️ এই ফোন নম্বরে ইতিমধ্যে রোগী আছে:\n"
                f"নাম: {existing.get('Full_Name')}\n"
                f"Patient ID: {existing.get('Patient_ID')}\n\n"
                "তবুও কি নতুন করে রেজিস্ট্রেশন করবে?",
                reply_markup=dup_keyboard,
            )
            return REG_PHONE_DUP
    await update.message.reply_text(
        "সমস্যা/অন্য কিছু থাকলে লেখো (না থাকলে - দাও):",
        reply_markup=_skip_keyboard(),
    )
    return REG_NOTE


async def reg_missing_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    keys = context.user_data.get("reg_missing_fields", [])
    if not keys:
        return await _reg_collect_missing_or_continue(update, context)
    if "," in text:
        parts = [x.strip() for x in text.split(",") if x.strip()]
    else:
        parts = text.split()
    if len(parts) != len(keys):
        label_map = dict(REG_REQUIRED_FIELDS)
        labels = ", ".join(label_map[k] for k in keys)
        await update.message.reply_text(
            f"⚠️ {len(keys)}টা তথ্য দরকার ছিল, পাওয়া গেছে {len(parts)}টা।\n"
            f"আবার একলাইনে লেখো: {labels}"
        )
        return REG_MISSING
    p = context.user_data.setdefault("new_patient", {})
    for k, v in zip(keys, parts):
        p[k] = v
    context.user_data.pop("reg_missing_fields", None)
    return await _reg_collect_missing_or_continue(update, context)'''

src = replace_once(src, old, new, "replace prefill helpers with missing-fields collector")

old = '''    await update.message.reply_text(
        "নতুন রোগীর পূর্ণ নাম লেখো:", reply_markup=ReplyKeyboardRemove()
    )
    return REG_NAME


async def reg_photo_receive'''
new = '''    return await _reg_collect_missing_or_continue(update, context)


async def reg_photo_receive'''
src = replace_once(src, old, new, "reg_photo_choice manual branch")

old = '''    if not found_lines:
        debug_line = f"\n\n🔧 Debug: {debug_error}" if debug_error else ""
        await update.message.reply_text(
            f"⚠️ ছবি থেকে তথ্য পড়া যায়নি। নিজে লিখতে হবে।{debug_line}\nনতুন রোগীর পূর্ণ নাম লেখো:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return REG_NAME'''
new = '''    if not found_lines:
        debug_line = f"\n\n🔧 Debug: {debug_error}" if debug_error else ""
        await update.message.reply_text(
            f"⚠️ ছবি থেকে তথ্য পড়া যায়নি। নিজে লিখতে হবে।{debug_line}",
        )
        return await _reg_collect_missing_or_continue(update, context)'''
src = replace_once(src, old, new, "reg_photo_receive no-fields-found branch")

old = '''async def reg_photo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("হ্যাঁ"):
        return await _reg_resume_after_prefill(update, context)
    context.user_data["new_patient"] = {}
    await update.message.reply_text(
        "ঠিক আছে, নতুন করে নাম লেখো:", reply_markup=ReplyKeyboardRemove()
    )
    return REG_NAME'''
new = '''async def reg_photo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("হ্যাঁ"):
        return await _reg_collect_missing_or_continue(update, context)
    context.user_data["new_patient"] = {}
    await update.message.reply_text(
        "ঠিক আছে, নতুন করে তথ্য দাও।", reply_markup=ReplyKeyboardRemove()
    )
    return await _reg_collect_missing_or_continue(update, context)'''
src = replace_once(src, old, new, "reg_photo_confirm")

old = '''async def reg_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_patient"]["Full_Name"] = update.message.text.strip()
    await update.message.reply_text("ফোন নম্বর লেখো:")
    return REG_PHONE


async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data["new_patient"]["Phone"] = phone
    existing = sheets.find_patient_by_phone(phone)
    if existing:
        dup_keyboard = ReplyKeyboardMarkup(
            [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
        )
        await update.message.reply_text(
            "⚠️ এই ফোন নম্বরে ইতিমধ্যে রোগী আছে:\n"
            f"নাম: {existing.get('Full_Name')}\n"
            f"Patient ID: {existing.get('Patient_ID')}\n\n"
            "তবুও কি নতুন করে রেজিস্ট্রেশন করবে?",
            reply_markup=dup_keyboard,
        )
        return REG_PHONE_DUP
    return await _reg_ask_address_or_note(update, context)


'''
src = replace_once(src, old, "", "remove dead reg_name/reg_phone")

old = '''    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        return await _reg_ask_address_or_note(update, context)
    context.user_data.pop("new_patient", None)
    await update.message.reply_text(
        "❌ ডুপ্লিকেট এড়াতে রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END'''
new = '''    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        await update.message.reply_text(
            "সমস্যা/অন্য কিছু থাকলে লেখো (না থাকলে - দাও):",
            reply_markup=_skip_keyboard(),
        )
        return REG_NOTE
    context.user_data.pop("new_patient", None)
    context.user_data.pop("reg_dup_checked", None)
    context.user_data.pop("reg_missing_fields", None)
    await update.message.reply_text(
        "❌ ডুপ্লিকেট এড়াতে রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END'''
src = replace_once(src, old, new, "reg_phone_dup_confirm yes branch")

old = '''async def reg_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_patient"]["Address"] = update.message.text.strip()
    await update.message.reply_text(
        "সমস্যা/বয়স/অন্য কিছু থাকলে এক লাইনে লেখো (না থাকলে - দাও):",
        reply_markup=_skip_keyboard(),
    )
    return REG_NOTE


'''
src = replace_once(src, old, "", "remove dead reg_address")

old = '''    p = context.user_data["new_patient"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"নাম: {p['Full_Name']}\nফোন: {p['Phone']}\nঠিকানা: {p['Address']}\n"
        f"নোট: {p['Diagnosis'] or '-'}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )'''
new = '''    p = context.user_data["new_patient"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\n\n"
        f"নাম: {p['Full_Name']}\nবয়স: {p.get('Age', '-')}\nফোন: {p['Phone']}\nঠিকানা: {p['Address']}\n"
        f"নোট: {p['Diagnosis'] or '-'}\n\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )'''
src = replace_once(src, old, new, "reg_confirm summary add Age")

old = '''    context.user_data.pop("new_patient", None)
    return ConversationHandler.END


async def reg_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_patient", None)
    await update.message.reply_text(
        "রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END'''
new = '''    context.user_data.pop("new_patient", None)
    context.user_data.pop("reg_dup_checked", None)
    context.user_data.pop("reg_missing_fields", None)
    return ConversationHandler.END


async def reg_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_patient", None)
    context.user_data.pop("reg_dup_checked", None)
    context.user_data.pop("reg_missing_fields", None)
    await update.message.reply_text(
        "রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END'''
src = replace_once(src, old, new, "reg_confirm/reg_cancel cleanup extra keys")

old = '''            REG_PHOTO_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_photo_confirm)],
            REG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_name)],
            REG_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone)],
            REG_PHONE_DUP: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone_dup_confirm)],
            REG_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_address)],
            REG_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_note)],'''
new = '''            REG_PHOTO_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_photo_confirm)],
            REG_MISSING: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_missing_receive)],
            REG_PHONE_DUP: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone_dup_confirm)],
            REG_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_note)],'''
src = replace_once(src, old, new, "ConversationHandler states dict")

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("✅ patch3.py applied successfully.")
