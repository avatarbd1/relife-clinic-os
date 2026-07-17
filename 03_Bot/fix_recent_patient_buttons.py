#!/usr/bin/env python3
"""
fix_recent_patient_buttons.py

সমস্যা: "সাম্প্রতিক রোগী" বাটন (recent-patient quick-pick) SEARCH স্টেজে
দেখানো হয়, কিন্তু বাটনের callback handler শুধু পরের (SELECT) স্টেজে
রেজিস্টার করা ছিল — তাই বাটনে চাপ দিলে কিছু হতো না।
অ্যাপয়েন্টমেন্ট, পেমেন্ট, ট্রিটমেন্ট নোট, ট্রিটমেন্ট প্ল্যান — ৪ জায়গাতেই এই বাগ ছিল।

ব্যবহার:
    cd ~/relife-clinic-os/03_Bot
    python3 fix_recent_patient_buttons.py

এটা স্বয়ংক্রিয়ভাবে:
  1. bot.py.before_recent_patient_fix নামে ব্যাকআপ নেবে
  2. bot.py-তে ৭টা নির্দিষ্ট পরিবর্তন করবে
  3. py_compile দিয়ে যাচাই করবে
  4. প্রতিটা পরিবর্তন ঠিকমতো হয়েছে কিনা রিপোর্ট করবে
"""

import shutil
import subprocess
import sys
from pathlib import Path

BOT_PATH = Path("bot.py")
BACKUP_PATH = Path("bot.py.before_recent_patient_fix")

# (description, old_str, new_str)
PATCHES = [
    (
        "treat_select_callback: recent-patient বাটনের জন্য fallback lookup",
        '    patient_id = query.data.replace("treatsel_", "")\n'
        '    results = context.user_data.get("treat_search_results", {})\n'
        "    patient = results.get(patient_id)\n",
        '    patient_id = query.data.replace("treatsel_", "")\n'
        '    results = context.user_data.get("treat_search_results", {})\n'
        "    patient = results.get(patient_id) or sheets.get_patient_by_id(patient_id)\n",
    ),
    (
        "tplan_select_callback: recent-patient বাটনের জন্য fallback lookup",
        '    patient_id = query.data.replace("tplansel_", "")\n'
        '    results = context.user_data.get("tplan_search_results", {})\n'
        "    patient = results.get(patient_id)\n",
        '    patient_id = query.data.replace("tplansel_", "")\n'
        '    results = context.user_data.get("tplan_search_results", {})\n'
        "    patient = results.get(patient_id) or sheets.get_patient_by_id(patient_id)\n",
    ),
    (
        "pay_select_callback: recent-patient বাটনের জন্য fallback lookup",
        '    patient_id = query.data.replace("paysel_", "")\n'
        '    results = context.user_data.get("pay_search_results", {})\n'
        "    patient = results.get(patient_id)\n",
        '    patient_id = query.data.replace("paysel_", "")\n'
        '    results = context.user_data.get("pay_search_results", {})\n'
        "    patient = results.get(patient_id) or sheets.get_patient_by_id(patient_id)\n",
    ),
    (
        "APT_SEARCH / APT_SELECT: apt_select_callback রেজিস্টার করা",
        '            APT_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_search)],\n'
        '            APT_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_select)],\n',
        '            APT_SEARCH: [\n'
        '                CallbackQueryHandler(apt_select_callback, pattern="^aptsel_"),\n'
        '                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_search),\n'
        '            ],\n'
        '            APT_SELECT: [\n'
        '                CallbackQueryHandler(apt_select_callback, pattern="^aptsel_"),\n'
        '                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_select),\n'
        '            ],\n',
    ),
    (
        "PAY_SEARCH: pay_select_callback রেজিস্টার করা",
        '            PAY_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_search)],\n',
        '            PAY_SEARCH: [\n'
        '                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),\n'
        '                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_search),\n'
        '            ],\n',
    ),
    (
        "TREAT_SEARCH: treat_select_callback রেজিস্টার করা",
        '            TREAT_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_search)],\n',
        '            TREAT_SEARCH: [\n'
        '                CallbackQueryHandler(treat_select_callback, pattern="^treatsel_"),\n'
        '                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_search),\n'
        '            ],\n',
    ),
    (
        "TPLAN_SEARCH: tplan_select_callback রেজিস্টার করা",
        '            TPLAN_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_search)],\n',
        '            TPLAN_SEARCH: [\n'
        '                CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_"),\n'
        '                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_search),\n'
        '            ],\n',
    ),
]


def main():
    if not BOT_PATH.exists():
        print(f"❌ {BOT_PATH} পাওয়া যায়নি। এই স্ক্রিপ্ট bot.py-এর একই ফোল্ডারে (03_Bot/) রেখে চালাও।")
        sys.exit(1)

    shutil.copy(BOT_PATH, BACKUP_PATH)
    print(f"✅ ব্যাকআপ নেওয়া হয়েছে: {BACKUP_PATH}")

    content = BOT_PATH.read_text(encoding="utf-8")
    applied, skipped = 0, 0

    for desc, old, new in PATCHES:
        if old not in content:
            if new in content:
                print(f"⏭️  ইতিমধ্যে ঠিক আছে (স্কিপ করা হলো): {desc}")
                skipped += 1
                continue
            print(f"⚠️  মিলছে না, ম্যানুয়ালি চেক করতে হবে: {desc}")
            continue
        content = content.replace(old, new, 1)
        print(f"✅ ঠিক করা হয়েছে: {desc}")
        applied += 1

    BOT_PATH.write_text(content, encoding="utf-8")

    print(f"\nমোট {applied}টা প্যাচ প্রয়োগ হয়েছে, {skipped}টা আগে থেকেই ঠিক ছিল।")

    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(BOT_PATH)],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print("✅ py_compile পাশ করেছে — bot.py এখন সিনট্যাক্স-ঠিক।")
    else:
        print("❌ py_compile ব্যর্থ হয়েছে! bot.py.before_recent_patient_fix থেকে রিস্টোর করো:")
        print(result.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
