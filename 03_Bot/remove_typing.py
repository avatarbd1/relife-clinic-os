#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# APT_DATE স্টেট থেকে MessageHandler সরাই
apt_date_state = re.search(r'APT_DATE:\s*\[(.*?)\]', content, re.DOTALL)
if apt_date_state:
    old_block = apt_date_state.group(0)
    # নতুন ব্লক: শুধু CallbackQueryHandler রাখি
    new_block = '''APT_DATE: [
                CallbackQueryHandler(apt_date_callback, pattern="^aptdate_"),
                CallbackQueryHandler(apt_date_done_callback, pattern="^aptdatedone_")
            ]'''
    content = content.replace(old_block, new_block, 1)
    print("✅ APT_DATE থেকে MessageHandler সরানো হয়েছে (টাইপ অপশন বাদ)")
else:
    print("❌ APT_DATE স্টেট খুঁজে পাওয়া যায়নি")

# apt_date ফাংশনটি আর দরকার নেই, কিন্তু রেখে দিলে সমস্যা নেই। আমরা চাইলে মুছতে পারি, কিন্তু আপাতত রাখি।

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ সম্পন্ন। এখন শুধু ক্যালেন্ডারের বাটনে ক্লিক করেই তারিখ বেছে নিতে পারবেন।")
