# -*- coding: utf-8 -*-
"""
Patch 4 (fix): Termux কীবোর্ডে পেস্ট করার সময় patch3.py-এর ভেতরের দুটো "\n"
এসকেপ প্রকৃত newline হয়ে গিয়েছিল, ফলে bot.py-তে SyntaxError হয়েছে
(unterminated string literal)। এই স্ক্রিপ্ট bot.py-এর সেই দুটো ভাঙা স্ট্রিং
নিরাপদে ঠিক করে দেয় — একটাই মেসেজকে দুটো আলাদা reply_text/edit_message_text
কলে ভেঙে দেওয়া হচ্ছে, যাতে আর কোনো \n escape লাগবে না।
Database/Sheets structure বা business logic কিছুই বদলায় না।
"""
import re
import sys

PATH = "bot.py"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

pattern = re.compile(
    r'await query\.edit_message_text\(\s*'
    r'"⬅️ রোগী খোঁজার ধাপে ফিরে যাওয়া হলো।\s*'
    r'রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো \(খুঁজতে\):"\s*\)'
)

matches = pattern.findall(src)
print(f"ভাঙা স্ট্রিং পাওয়া গেছে: {len(matches)} টা")

if len(matches) != 2:
    print("❌ প্রত্যাশিত ঠিক ২টা ভাঙা স্ট্রিং পাওয়া যায়নি।")
    print("ফাইল অপরিবর্তিত রাখা হলো, কিছু সেভ করা হয়নি।")
    sys.exit(1)

replacement = (
    'await query.edit_message_text("⬅️ রোগী খোঁজার ধাপে ফিরে যাওয়া হলো।")\n'
    '    await query.message.reply_text("রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):")'
)

new_src, n = pattern.subn(replacement, src)
if n != 2:
    print(f"❌ প্রত্যাশিত ২টা প্রতিস্থাপন হয়নি (হয়েছে {n} টা)। থেমে গেলাম।")
    sys.exit(1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(new_src)

print("✅ দুটো ভাঙা স্ট্রিং ঠিক করা হয়েছে।")
print("এখন: python -m py_compile bot.py  দিয়ে চেক করো, তারপর কমিট/পুশ করো।")
