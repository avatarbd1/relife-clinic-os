#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# apt_conv কনভারসেশন হ্যান্ডলার খুঁজি
apt_conv_pattern = r'apt_conv = ConversationHandler\([^)]*?(?:\[[^\]]*?\])+[^)]*?\)'
match = re.search(apt_conv_pattern, content, re.DOTALL)
if not match:
    print("❌ apt_conv খুঁজে পাওয়া যায়নি।")
    exit(1)

apt_conv = match.group(0)

# APT_DATE স্টেটে CallbackQueryHandler যোগ করি
if "CallbackQueryHandler(apt_date_callback, pattern=\"^aptdate_\")" not in apt_conv:
    apt_conv = re.sub(
        r'(APT_DATE:\s*\[)',
        r'\1\n                CallbackQueryHandler(apt_date_callback, pattern="^aptdate_"),',
        apt_conv
    )
    print("✅ APT_DATE-তে apt_date_callback যোগ হয়েছে")

if "CallbackQueryHandler(apt_date_done_callback, pattern=\"^aptdatedone_\")" not in apt_conv:
    apt_conv = re.sub(
        r'(APT_DATE:\s*\[[^\]]*?)',
        r'\1\n                CallbackQueryHandler(apt_date_done_callback, pattern="^aptdatedone_"),',
        apt_conv
    )
    print("✅ APT_DATE-তে apt_date_done_callback যোগ হয়েছে")

# APT_REPEAT স্টেটে CallbackQueryHandler যোগ করি
if "CallbackQueryHandler(apt_repeat_callback, pattern=\"^aptrepeat_\")" not in apt_conv:
    if "APT_REPEAT:" in apt_conv:
        apt_conv = re.sub(
            r'(APT_REPEAT:\s*\[)',
            r'\1\n                CallbackQueryHandler(apt_repeat_callback, pattern="^aptrepeat_"),',
            apt_conv
        )
        print("✅ APT_REPEAT-তে apt_repeat_callback যোগ হয়েছে")
    else:
        print("⚠️ APT_REPEAT স্টেট নেই, পরে যোগ হবে")

# পুরনো apt_conv প্রতিস্থাপন
content = content.replace(match.group(0), apt_conv, 1)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

try:
    compile(content, "bot.py", "exec")
    print("✅ সিনট্যাক্স ঠিক আছে")
except SyntaxError as e:
    print(f"❌ সিনট্যাক্স এরর: {e}")

