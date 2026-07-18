with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

# ১. প্রোফাইল কার্ডে "রিপোর্ট" বাটন যোগ
old_button = 'InlineKeyboardButton("🔙 তালিকায় ফিরুন", callback_data="plistact_back")'
new_button = 'InlineKeyboardButton("📎 রিপোর্ট", callback_data=f"plistact_report_{patient_id}")],\n        [' + old_button
if old_button in content and 'plistact_report_' not in content:
    content = content.replace(old_button, new_button, 1)
    print("✅ ১. বাটন যোগ হয়েছে")
else:
    print("⚠️ ১. বাটন অ্যাঙ্কর পাওয়া যায়নি বা আগেই যোগ করা আছে")

# ২. নতুন হ্যান্ডলার ফাংশনগুলো main()-এর ঠিক আগে যোগ
new_functions = '''
REPORT_UPLOAD = "REPORT_UPLOAD"


async def plist_action_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_report_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["report_patient"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
    }
    await query.edit_message_text(
        f"📎 {patient.get('Full_Name')} ({patient_id})-এর জন্য রিপোর্ট (ছবি/ফাইল) পাঠাও।\\n"
        "একাধিক ফাইল পাঠাতে চাইলে একটার পর একটা পাঠাতে থাকো। শেষ হলে /cancel দাও।"
    )
    return REPORT_UPLOAD


async def report_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    import os
    import tempfile
    import drive as drive_module

    staff = context.user_data.get("staff", {})
    rp = context.user_data.get("report_patient")
    if not rp:
        await update.message.reply_text("❌ সমস্যা হয়েছে, আবার 📋 রোগীর তালিকা থেকে শুরু করো।")
        return ConversationHandler.END

    file_obj = None
    file_name = ""
    file_type = ""
    if update.message.photo:
        file_obj = await update.message.photo[-1].get_file()
        file_name = f"{rp['Patient_ID']}_{file_obj.file_unique_id}.jpg"
        file_type = "Photo"
    elif update.message.document:
        doc = update.message.document
        file_obj = await doc.get_file()
        file_name = doc.file_name or f"{rp['Patient_ID']}_{doc.file_unique_id}"
        file_type = "Document"
    else:
        await update.message.reply_text("❌ শুধু ছবি বা ফাইল পাঠাও।")
        return REPORT_UPLOAD

    tmp_dir = tempfile.gettempdir()
    local_path = os.path.join(tmp_dir, file_name)
    await file_obj.download_to_drive(local_path)

    try:
        drive_id, drive_link = drive_module.upload_file_to_drive(local_path, file_name)
        report_id = sheets.add_report({
            "Patient_ID": rp["Patient_ID"],
            "Patient_Name": rp["Patient_Name"],
            "File_Telegram_ID": file_obj.file_id,
            "File_Name": file_name,
            "File_Type": file_type,
            "File_Drive_Link": drive_link,
        }, uploaded_by=staff.get("Full_Name", "Unknown"))
        await update.message.reply_text(
            f"✅ রিপোর্ট সেভ হয়েছে! Report ID: {report_id}\\n"
            "আরেকটা পাঠাতে চাইলে পাঠাও, নাহলে /cancel দাও।"
        )
    except Exception as e:
        logger.exception("report_receive ব্যর্থ হয়েছে")
        await update.message.reply_text(f"❌ আপলোড করতে সমস্যা হয়েছে।\\nError: {e}")
    finally:
        try:
            os.remove(local_path)
        except OSError:
            pass
    return REPORT_UPLOAD


async def report_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("report_patient", None)
    await update.effective_message.reply_text(
        "রিপোর্ট আপলোড শেষ।",
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END


'''
anchor2 = 'def main():'
if anchor2 in content and 'def plist_action_report' not in content:
    content = content.replace(anchor2, new_functions + anchor2, 1)
    print("✅ ২. হ্যান্ডলার ফাংশন যোগ হয়েছে")
else:
    print("⚠️ ২. main() অ্যাঙ্কর পাওয়া যায়নি বা আগেই যোগ করা আছে")

# ৩. ConversationHandler রেজিস্টার করা
anchor3 = 'app.add_handler(CallbackQueryHandler(plist_action_hist, pattern="^plistact_hist_"))'
new_reg = anchor3 + '''
    report_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(plist_action_report, pattern="^plistact_report_")],
        states={
            REPORT_UPLOAD: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, report_receive),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", report_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(report_conv)'''
if anchor3 in content and 'report_conv' not in content.split(anchor3)[0]:
    content = content.replace(anchor3, new_reg, 1)
    print("✅ ৩. হ্যান্ডলার রেজিস্টার হয়েছে")
else:
    print("⚠️ ৩. রেজিস্ট্রেশন অ্যাঙ্কর পাওয়া যায়নি বা আগেই যোগ করা আছে")

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)
