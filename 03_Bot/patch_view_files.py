with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ১. প্রোফাইল কার্ডে "ফাইল দেখুন" বাটন যোগ
old_button = 'InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data="plistact_back")'
new_button = 'InlineKeyboardButton("👁️ ফাইল দেখুন", callback_data=f"plistact_viewfiles_{patient_id}")],\n        [' + old_button
if old_button in content and 'plistact_viewfiles_' not in content:
    content = content.replace(old_button, new_button, 1)
    print("✅ ১. বাটন যোগ হয়েছে")
else:
    print("⚠️ ১. বাটন অ্যাঙ্কর পাওয়া যায়নি বা আগেই যোগ করা আছে")

# ২. নতুন হ্যান্ডলার ফাংশন main()-এর আগে যোগ
new_functions = '''
async def plist_action_viewfiles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_viewfiles_", "")
    staff = context.user_data.get("staff", {})
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return
    role = staff.get("Role", "").strip()
    allowed = role in ("Owner", "Manager") or (
        role == "Therapist" and roles.is_therapist_owner_of_patient(staff.get("Full_Name", ""), patient)
    )
    if not allowed:
        await query.edit_message_text("⛔ এই রোগীর ফাইল দেখার অনুমতি তোমার নেই।")
        return
    reports = sheets.get_reports_for_patient(patient_id)
    if not reports:
        await query.edit_message_text(f"📂 {patient.get('Full_Name')}-এর কোনো ফাইল এখনো আপলোড হয়নি।")
        return
    buttons = [
        [InlineKeyboardButton(
            f"{r.get('File_Type', 'ফাইল')} — {r.get('Upload_Date', '')}",
            callback_data=f"plistact_getfile_{r.get('Report_ID', '')}",
        )]
        for r in reversed(reports)
    ]
    buttons.append([InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data="plistact_back")])
    await query.edit_message_text(
        f"📂 {patient.get('Full_Name')}-এর ফাইল ({len(reports)}টি) — দেখতে চাপো:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def plist_action_getfile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = query.data.replace("plistact_getfile_", "")
    staff = context.user_data.get("staff", {})
    record = sheets.get_report_by_id(report_id)
    if not record:
        await query.message.reply_text("❌ ফাইল পাওয়া যায়নি।")
        return
    patient = sheets.get_patient_by_id(record.get("Patient_ID", ""))
    role = staff.get("Role", "").strip()
    allowed = patient and (
        role in ("Owner", "Manager") or (
            role == "Therapist" and roles.is_therapist_owner_of_patient(staff.get("Full_Name", ""), patient)
        )
    )
    if not allowed:
        await query.message.reply_text("⛔ এই ফাইল দেখার অনুমতি তোমার নেই।")
        return
    caption = f"{record.get('File_Type', '')} — {record.get('Upload_Date', '')} ({record.get('Patient_Name', '')})"
    tg_id = record.get("File_Telegram_ID", "")
    sent = False
    if tg_id:
        try:
            await context.bot.send_document(chat_id=query.message.chat_id, document=tg_id, caption=caption)
            sent = True
        except Exception:
            logger.exception("Telegram file_id দিয়ে পাঠাতে ব্যর্থ")
    if not sent:
        link = record.get("File_Drive_Link", "")
        if link:
            await query.message.reply_text(f"{caption}\\nDrive লিংক: {link}")
        else:
            await query.message.reply_text("❌ ফাইলটা এখন খুলতে পারা যাচ্ছে না।")


'''
anchor2 = 'def main():'
if anchor2 in content and 'def plist_action_viewfiles' not in content:
    content = content.replace(anchor2, new_functions + anchor2, 1)
    print("✅ ২. হ্যান্ডলার ফাংশন যোগ হয়েছে")
else:
    print("⚠️ ২. main() অ্যাঙ্কর পাওয়া যায়নি বা আগেই যোগ করা আছে")

# ৩. হ্যান্ডলার রেজিস্টার করা
anchor3 = 'app.add_handler(CallbackQueryHandler(patient_list_back_callback, pattern="^plistact_back$"))'
new_reg = anchor3 + '''
    app.add_handler(CallbackQueryHandler(plist_action_viewfiles, pattern="^plistact_viewfiles_"))
    app.add_handler(CallbackQueryHandler(plist_action_getfile, pattern="^plistact_getfile_"))'''
if anchor3 in content and 'plist_action_viewfiles, pattern' not in content.split(anchor3)[0]:
    content = content.replace(anchor3, new_reg, 1)
    print("✅ ৩. হ্যান্ডলার রেজিস্টার হয়েছে")
else:
    print("⚠️ ৩. রেজিস্ট্রেশন অ্যাঙ্কর পাওয়া যায়নি বা আগেই যোগ করা আছে")

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)
