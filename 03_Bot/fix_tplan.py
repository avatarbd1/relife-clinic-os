#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# TPLAN টাপল খুঁজি
old_tplan = r'\(\s*TPLAN_SEARCH,.*?\) = range\(29, 37\)'
match = re.search(old_tplan, content, re.DOTALL)
if match:
    block = match.group(0)
    if "TPLAN_CARRYOVER" not in block:
        new_block = block.replace("TPLAN_SELECT,", "TPLAN_SELECT,\n    TPLAN_CARRYOVER,")
        new_block = new_block.replace("range(29, 37)", "range(30, 39)")
        content = content.replace(block, new_block, 1)
        print("✅ TPLAN_CARRYOVER যোগ ও range(30, 39) করা হয়েছে।")
    else:
        print("⏩ TPLAN_CARRYOVER ইতিমধ্যে আছে।")
else:
    if "TPLAN_CARRYOVER" in content:
        print("⏩ TPLAN_CARRYOVER ইতিমধ্যে কোডে আছে।")
    else:
        print("❌ TPLAN টাপল খুঁজে পাওয়া যায়নি।")
        exit(1)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

try:
    compile(content, "bot.py", "exec")
    print("✅ সিনট্যাক্স ঠিক আছে।")
except SyntaxError as e:
    print(f"❌ সিনট্যাক্স এরর: {e}")
