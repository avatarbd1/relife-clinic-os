import re

PATH = "bot.py"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

TOPLEVEL_DEF = re.compile(r'^(async def |def )', re.MULTILINE)


def find_func_span(src, name):
    start_pat = re.compile(rf'^async def {re.escape(name)}\(', re.MULTILINE)
    m = start_pat.search(src)
    if not m:
        raise SystemExit(f"❌ FAILED: function '{name}' not found in bot.py")
    start = m.start()
    m2 = TOPLEVEL_DEF.search(src, m.end())
    end = m2.start() if m2 else len(src)
    return start, end


def replace_func(src, name, new_text):
    start, end = find_func_span(src, name)
    if not new_text.endswith("\n\n\n"):
        new_text = new_text.rstrip("\n") + "\n\n\n"
    return src[:start] + new_text + src[end:]


def remove_func(src, name):
    start, end = find_func_span(src, name)
    return src[:start] + src[end:]


old = 'REG_PHOTO_CHOICE, REG_PHOTO_WAIT, REG_PHOTO_CONFIRM = range(90, 93)'
new = 'REG_PHOTO_CHOICE, REG_PHOTO_WAIT, REG_PHOTO_CONFIRM, REG_MISSING = range(90, 94)'
if src.count(old) != 1:
    raise SystemExit(f"❌ FAILED: state-range line found {src.count(old)} times (need 1)")
src = src.replace(old, new, 1)

src = remove_func(src, "_reg_ask_address_or_note")

new_helpers = '''REG_REQUIRED_FIELDS = [
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
            f"এই তথ্যগুলো একলাইনে লেখো: {labels}\\n\\nযেমন: {example}",
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
                "⚠️ এই ফোন নম্বরে ইতিমধ্যে রোগী আছে:\\n"
                f"নাম: {existing.get('Full_Name')}\\n"
                f"Patient ID: {existing.get('Patient_ID')}\\n\\n"
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
            f"⚠️ {len(keys)}টা তথ্য দরকার ছিল, পাওয়া গেছে {len(parts)}টা।\\n"
            f"আবার একলাইনে লেখো: {labels}"
        )
        return REG_MISSING
    p = context.user_data.setdefault("new_patient", {})
    for k, v in zip(keys, parts):
        p[k] = v
    context.user_data.pop("reg_missing_fields", None)
    return await _reg_collect_missing_or_continue(update, context)
'''
src = replace_func(src, "_reg_resume_after_prefill", new_helpers)

new_photo_choice = '''async def reg_photo_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("📷"):
        await update.message.reply_text(
            "রোগীর report/prescription/x-ray-এর ছবিটা পাঠাও:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return REG_PHOTO_WAIT
    return await _reg_collect_missing_or_continue(update, context)
'''
src = replace_func(src, "reg_photo_choice", new_photo_choice)

new_photo_receive = '''async def reg_photo_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    image_bytes = bytes(await tg_file.download_as_bytearray())
    await update.message.reply_text("⏳ ছবিটা পড়া হচ্ছে...")
    debug_error = None
    try:
        extracted = photo_extract.extract_from_photo(image_bytes)
    except Exception as e:
        logger.exception("photo_extract failed")
        extracted = None
        debug_error = f"{type(e).__name__}: {e}"

    field_map = {
        "full_name": "Full_Name",
        "age": "Age",
        "phone": "Phone",
        "address": "Address",
        "gender": "Gender",
    }
    p = context.user_data.setdefault("new_patient", {})
    found_lines = []
    if extracted:
        for src_key, dst_key in field_map.items():
            val = extracted.get(src_key)
            if val:
                p[dst_key] = str(val).strip()
                found_lines.append(f"{dst_key}: {p[dst_key]}")

    if not found_lines:
        debug_line = f"\\n\\n🔧 Debug: {debug_error}" if debug_error else ""
        await update.message.reply_text(
            f"⚠️ ছবি থেকে তথ্য পড়া যায়নি। নিজে লিখতে হবে।{debug_line}",
        )
        return await _reg_collect_missing_or_continue(update, context)

    summary = "📋 ছবি থেকে এই তথ্য পাওয়া গেছে:\\n\\n" + "\\n".join(found_lines)
    summary += "\\n\\nঠিক আছে?"
    confirm_kb = ReplyKeyboardMarkup(
        [["হ্যাঁ, ঠিক আছে", "না, নিজে লিখব"]],
        resize_keyboard=True, one_time_keyboard=True,
    )
    await update.message.reply_text(summary, reply_markup=confirm_kb)
    return REG_PHOTO_CONFIRM
'''
src = replace_func(src, "reg_photo_receive", new_photo_receive)

new_photo_confirm = '''async def reg_photo_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.startswith("হ্যাঁ"):
        return await _reg_collect_missing_or_continue(update, context)
    context.user_data["new_patient"] = {}
    await update.message.reply_text(
        "ঠিক আছে, নতুন করে তথ্য দাও।", reply_markup=ReplyKeyboardRemove()
    )
    return await _reg_collect_missing_or_continue(update, context)
'''
src = replace_func(src, "reg_photo_confirm", new_photo_confirm)

src = remove_func(src, "reg_name")
src = remove_func(src, "reg_phone")

new_phone_dup_confirm = '''async def reg_phone_dup_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
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
    return ConversationHandler.END
'''
src = replace_func(src, "reg_phone_dup_confirm", new_phone_dup_confirm)

src = remove_func(src, "reg_address")

new_reg_confirm = '''async def reg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        patient_id = sheets.add_patient(
            context.user_data["new_patient"],
            created_by=staff.get("Full_Name", "Unknown"),
        )
        await update.message.reply_text(
            f"✅ রোগী রেজিস্ট্রেশন সম্পন্ন! Patient ID: {patient_id}",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
        new_patient_row = sheets.get_patient_by_id(patient_id)
        if new_patient_row:
            await update.message.reply_text(
                _patient_card_text(new_patient_row),
                reply_markup=_patient_card_keyboard(patient_id),
            )
    else:
        await update.message.reply_text(
            "❌ বাতিল করা হয়েছে।",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("new_patient", None)
    context.user_data.pop("reg_dup_checked", None)
    context.user_data.pop("reg_missing_fields", None)
    return ConversationHandler.END
'''
src = replace_func(src, "reg_confirm", new_reg_confirm)

new_reg_cancel = '''async def reg_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("new_patient", None)
    context.user_data.pop("reg_dup_checked", None)
    context.user_data.pop("reg_missing_fields", None)
    await update.message.reply_text(
        "রেজিস্ট্রেশন বাতিল করা হয়েছে।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END
'''
src = replace_func(src, "reg_cancel", new_reg_cancel)

old_summary = '''        f"নাম: {p['Full_Name']}\\nফোন: {p['Phone']}\\nঠিকানা: {p['Address']}\\n"'''
new_summary = '''        f"নাম: {p['Full_Name']}\\nবয়স: {p.get('Age', '-')}\\nফোন: {p['Phone']}\\nঠিকানা: {p['Address']}\\n"'''
if src.count(old_summary) == 1:
    src = src.replace(old_summary, new_summary, 1)
else:
    print(f"⚠️ WARNING: could not patch Age into confirm summary (found {src.count(old_summary)} matches) — skipped, fix manually")

old_states_pat = re.compile(
    r'REG_NAME:\s*\[.*?\],\s*\n\s*REG_PHONE:\s*\[.*?\],\s*\n\s*REG_PHONE_DUP:\s*\[.*?\],\s*\n\s*REG_ADDRESS:\s*\[.*?\],\s*\n\s*REG_NOTE:\s*\[.*?\],',
    re.DOTALL,
)
new_states = (
    'REG_MISSING: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_missing_receive)],\n'
    '            REG_PHONE_DUP: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone_dup_confirm)],\n'
    '            REG_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_note)],'
)
matches = old_states_pat.findall(src)
if len(matches) != 1:
    raise SystemExit(f"❌ FAILED: ConversationHandler states block found {len(matches)} times (need 1)")
src = old_states_pat.sub(new_states, src, count=1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("✅ patch3_v2.py applied successfully.")
