#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. APT টাপলে APT_REPEAT যোগ ও range আপডেট
old_apt = r'\(\s*REG_NAME,.*?\) = range\(13\)'
match = re.search(old_apt, content, re.DOTALL)
if match:
    block = match.group(0)
    if "APT_REPEAT" not in block:
        new_block = block.replace("APT_DATE,", "APT_DATE,\n    APT_REPEAT,")
        new_block = new_block.replace("range(13)", "range(14)")
        content = content.replace(block, new_block, 1)
        print("✅ APT টাপলে APT_REPEAT যোগ ও range(14) করা হয়েছে।")
    else:
        print("⏩ APT_REPEAT ইতিমধ্যে আছে।")
else:
    print("❌ APT টাপল খুঁজে পাওয়া যায়নি।")
    exit(1)

# 2. PAY range আপডেট
if "range(14, 20)" not in content:
    content = content.replace("range(13, 19)", "range(14, 20)")
    print("✅ PAY range আপডেট: range(14, 20)")
else:
    print("⏩ PAY range ইতিমধ্যে আপডেটেড।")

# 3. TREAT range আপডেট
if "range(20, 30)" not in content:
    content = content.replace("range(19, 29)", "range(20, 30)")
    print("✅ TREAT range আপডেট: range(20, 30)")
else:
    print("⏩ TREAT range ইতিমধ্যে আপডেটেড।")

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

# সিনট্যাক্স চেক
try:
    compile(content, "bot.py", "exec")
    print("✅ সিনট্যাক্স ঠিক আছে।")
except SyntaxError as e:
    print(f"❌ সিনট্যাক্স এরর: {e}")

