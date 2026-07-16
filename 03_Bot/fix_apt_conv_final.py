#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# apt_conv ব্লক খুঁজি
start = content.find("apt_conv = ConversationHandler(")
if start == -1:
    print("❌ apt_conv খুঁজে পাওয়া যায়নি")
    exit(1)

# শেষ বন্ধনী খুঁজি
end = start
depth = 0
for i, ch in enumerate(content[start:], start):
    if ch == '(':
        depth += 1
    elif ch == ')':
        depth -= 1
        if depth == 0:
            end = i + 1
            break

old_block = content[start:end]

# নতুন ব্লক তৈরি (সব হ্যান্ডলারসহ)
new_block = '''apt_conv = ConversationHandler(
    entry_points=[CommandHandler("apt", apt_start)],
    states={
        APT_SEARCH: [
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_search)
        ],
        APT_SELECT: [
            CallbackQueryHandler(apt_select, pattern="^aptsel_")
        ],
        APT_DATE: [
            CallbackQueryHandler(apt_date_callback, pattern="^aptdate_"),
            CallbackQueryHandler(apt_date_done_callback, pattern="^aptdatedone_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_date)
        ],
        APT_REPEAT: [
            CallbackQueryHandler(apt_repeat_callback, pattern="^aptrepeat_")
        ],
        APT_TIME: [
            CallbackQueryHandler(apt_time_callback, pattern="^apttime_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_time)
        ],
        APT_THERAPIST: [
            CallbackQueryHandler(apt_therapist_callback, pattern="^aptther_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_therapist)
        ],
        APT_CONFIRM: [
            MessageHandler(filters.Regex("^(হ্যাঁ|হা|yes|y)$"), apt_confirm),
            MessageHandler(filters.Regex("^(না|no|n)$"), apt_confirm)
        ]
    },
    fallbacks=[
        CommandHandler("cancel", apt_cancel),
        MessageHandler(filters.Regex(_ALL_MENU_REGEX) & ~filters.COMMAND, apt_cancel)
    ],
    per_message=False
)'''

content = content.replace(old_block, new_block, 1)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

print("✅ apt_conv সম্পূর্ণভাবে রিপ্লেস করা হয়েছে")
print("✅ সব CallbackQueryHandler যুক্ত হয়েছে")
