path = "/data/data/com.termux/files/home/relife-clinic-os/03_Bot/bot.py"
src = open(path, encoding="utf-8").read()

# 1. merge reg_phone + reg_phone_confirm into one single-entry function
old_funcs = '''async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data["_phone_pending"] = phone
    await update.message.reply_text("ফোন নম্বরটা আবার লেখো (নিশ্চিত করার জন্য):")
    return REG_PHONE_CONFIRM


async def reg_phone_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    typed_again = update.message.text.strip()
    pending = context.user_data.get("_phone_pending", "")
    if typed_again != pending:
        await update.message.reply_text(
            "⚠️ দুইবার লেখা নম্বর মেলেনি। আবার প্রথম থেকে ফোন নম্বর লেখো:"
        )
        return REG_PHONE

    phone = pending
    context.user_data["new_patient"]["Phone"] = phone
    existing = sheets.find_patient_by_phone(phone)
    if existing:
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
    await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
    return REG_ADDRESS'''

new_funcs = '''async def reg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data["new_patient"]["Phone"] = phone
    existing = sheets.find_patient_by_phone(phone)
    if existing:
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
    await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
    return REG_ADDRESS'''

assert src.count(old_funcs) == 1, f"funcs anchor found {src.count(old_funcs)} times"
src = src.replace(old_funcs, new_funcs, 1)

# 2. remove REG_PHONE_CONFIRM from reg_conv states dict
old_state_line = '            REG_PHONE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), reg_phone_confirm)],\n'
assert src.count(old_state_line) == 1, f"state anchor found {src.count(old_state_line)} times"
src = src.replace(old_state_line, "", 1)

open(path, "w", encoding="utf-8").write(src)
print("✅ ফোন নম্বর ডাবল-এন্ট্রি বাদ দেওয়া হয়েছে")
