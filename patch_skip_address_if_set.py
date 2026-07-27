path = "/data/data/com.termux/files/home/relife-clinic-os/03_Bot/bot.py"
src = open(path, encoding="utf-8").read()

old_helper_target = '''async def _reg_resume_after_prefill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:'''
new_helper = '''async def _reg_ask_address_or_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    p = context.user_data.get("new_patient", {})
    if not p.get("Address"):
        await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
        return REG_ADDRESS
    await update.message.reply_text(
        "সমস্যা/বয়স/অন্য কিছু থাকলে এক লাইনে লেখো (না থাকলে - দাও):",
        reply_markup=_skip_keyboard(),
    )
    return REG_NOTE


async def _reg_resume_after_prefill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:'''
assert src.count(old_helper_target) == 1, f"helper anchor found {src.count(old_helper_target)} times"
src = src.replace(old_helper_target, new_helper, 1)

old_phone_tail = '''        return REG_PHONE_DUP
    await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
    return REG_ADDRESS


async def reg_phone_dup_confirm'''
new_phone_tail = '''        return REG_PHONE_DUP
    return await _reg_ask_address_or_note(update, context)


async def reg_phone_dup_confirm'''
assert src.count(old_phone_tail) == 1, f"phone tail anchor found {src.count(old_phone_tail)} times"
src = src.replace(old_phone_tail, new_phone_tail, 1)

old_dup_tail = '''    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        await update.message.reply_text("ঠিকানা লেখো:", reply_markup=ReplyKeyboardRemove())
        return REG_ADDRESS
    context.user_data.pop("new_patient", None)'''
new_dup_tail = '''    if text in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        return await _reg_ask_address_or_note(update, context)
    context.user_data.pop("new_patient", None)'''
assert src.count(old_dup_tail) == 1, f"dup tail anchor found {src.count(old_dup_tail)} times"
src = src.replace(old_dup_tail, new_dup_tail, 1)

open(path, "w", encoding="utf-8").write(src)
print("✅ আগে থেকে extract হওয়া ঠিকানা আর দ্বিতীয়বার জিজ্ঞেস করবে না")
