#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. apt_select ফাংশন আপডেট
apt_select_pattern = r'(async def apt_select\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?return APT_DATE)'
match = re.search(apt_select_pattern, content, re.DOTALL)
if match:
    old_func = match.group(0)
    # চেক করি _date_multi_keyboard আছে কিনা
    if "_date_multi_keyboard" not in old_func:
        # রিপ্লেস
        new_func = old_func.replace(
            'reply_markup=_date_keyboard()',
            'reply_markup=_date_multi_keyboard(set())'
        )
        # apt_selected_dates সেট করা আছে কিনা
        if 'apt_selected_dates' not in new_func:
            # context.user_data.pop এর পর যোগ করি
            new_func = new_func.replace(
                'context.user_data.pop("apt_search_results", None)',
                'context.user_data.pop("apt_search_results", None)\n    context.user_data["apt_selected_dates"] = set()'
            )
        content = content.replace(old_func, new_func, 1)
        print("✅ apt_select আপডেট করা হয়েছে")
    else:
        print("⏩ apt_select ইতিমধ্যে আপডেটেড")
else:
    print("❌ apt_select খুঁজে পাওয়া যায়নি")

# 2. plist_action_apt ফাংশন আপডেট
plist_pattern = r'(async def plist_action_apt\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?return APT_DATE)'
match = re.search(plist_pattern, content, re.DOTALL)
if match:
    old_func = match.group(0)
    if "_date_multi_keyboard" not in old_func:
        new_func = old_func.replace(
            'reply_markup=_date_keyboard()',
            'reply_markup=_date_multi_keyboard(set())'
        )
        if 'apt_selected_dates' not in new_func:
            new_func = new_func.replace(
                'context.user_data["new_appointment"] = {',
                'context.user_data["apt_selected_dates"] = set()\n    context.user_data["new_appointment"] = {'
            )
        content = content.replace(old_func, new_func, 1)
        print("✅ plist_action_apt আপডেট করা হয়েছে")
    else:
        print("⏩ plist_action_apt ইতিমধ্যে আপডেটেড")
else:
    print("❌ plist_action_apt খুঁজে পাওয়া যায়নি")

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

try:
    compile(content, "bot.py", "exec")
    print("✅ সিনট্যাক্স ঠিক আছে")
except SyntaxError as e:
    print(f"❌ সিনট্যাক্স এরর: {e}")

