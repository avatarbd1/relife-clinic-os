path = "/data/data/com.termux/files/home/relife-clinic-os/03_Bot/bot.py"
src = open(path, encoding="utf-8").read()

old = '''async def reg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    else:'''

new = '''async def reg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    else:'''

assert src.count(old) == 1, f"anchor found {src.count(old)} times"
src = src.replace(old, new, 1)

open(path, "w", encoding="utf-8").write(src)
print("✅ রেজিস্ট্রেশন শেষে patient detail menu যুক্ত হয়েছে")
