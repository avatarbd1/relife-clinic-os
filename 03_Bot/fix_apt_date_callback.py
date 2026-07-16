#!/usr/bin/env python3
import re
with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()
old = r'async def apt_date_callback\(update: Update, context: ContextTypes\.DEFAULT_TYPE\):.*?(?=\n\nasync def apt_date\(|\Z)'
match = re.search(old, content, re.DOTALL)
if match:
    old_func = match.group(0)
    new_func = '''async def apt_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.replace("aptdate_", "")
    selected = context.user_data.setdefault("apt_selected_dates", set())
    if date_str in selected:
        selected.discard(date_str)
    else:
        selected.add(date_str)
    await query.edit_message_reply_markup(reply_markup=_date_multi_keyboard(selected))
    return APT_DATE'''
    content = content.replace(old_func, new_func, 1)
    with open("bot.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ apt_date_callback আপডেট হয়েছে")
else:
    print("❌ খুঁজে পাওয়া যায়নি")
