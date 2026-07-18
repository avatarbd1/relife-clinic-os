with open('bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''    try:
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
    finally:'''

new_block = '''    drive_link = ""
    try:
        _drive_id, drive_link = drive_module.upload_file_to_drive(local_path, file_name)
    except Exception:
        logger.exception("Drive আপলোড ব্যর্থ হয়েছে, শুধু Telegram-এ সংরক্ষিত থাকবে")

    try:
        report_id = sheets.add_report({
            "Patient_ID": rp["Patient_ID"],
            "Patient_Name": rp["Patient_Name"],
            "File_Telegram_ID": file_obj.file_id,
            "File_Name": file_name,
            "File_Type": file_type,
            "File_Drive_Link": drive_link,
        }, uploaded_by=staff.get("Full_Name", "Unknown"))
        note = "" if drive_link else "\\n(⚠️ Drive ব্যাকআপ হয়নি, শুধু Telegram-এ সংরক্ষিত আছে)"
        await update.message.reply_text(
            f"✅ রিপোর্ট সেভ হয়েছে! Report ID: {report_id}{note}\\n"
            "আরেকটা পাঠাতে চাইলে পাঠাও, নাহলে /cancel দাও।"
        )
    except Exception as e:
        logger.exception("report_receive শীটে সেভ করতে ব্যর্থ হয়েছে")
        await update.message.reply_text(f"❌ সেভ করতে সমস্যা হয়েছে।\\nError: {e}")
    finally:'''

if old_block in content:
    content = content.replace(old_block, new_block, 1)
    print("✅ report_receive প্যাচ হয়েছে")
else:
    print("⚠️ অ্যাঙ্কর মেলেনি — bot.py-তে ম্যানুয়ালি চেক করা লাগবে")

with open('bot.py', 'w', encoding='utf-8') as f:
    f.write(content)
