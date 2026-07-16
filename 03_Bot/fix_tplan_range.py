#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# TPLAN টাপল খুঁজি
pattern = r'(\(\s*TPLAN_SEARCH,.*?TPLAN_MACHINES,\s*\)\s*=\s*range\([0-9, ]+\))'
match = re.search(pattern, content, re.DOTALL)
if match:
    block = match.group(0)
    # ভেরিয়েবল সংখ্যা গুনি
    var_count = block.count("TPLAN_")
    # সঠিক range বের করি: ধরি start 30 (কারণ আগের টাপল 29 পর্যন্ত ছিল)
    start = 30
    end = start + var_count
    new_range = f"range({start}, {end})"
    # পুরনো range রিপ্লেস
    new_block = re.sub(r'range\([0-9, ]+\)', new_range, block)
    content = content.replace(block, new_block, 1)
    print(f"✅ TPLAN টাপল আপডেট: {var_count}টি ভেরিয়েবল, range({start}, {end})")
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

