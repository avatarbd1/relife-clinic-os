#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. apt_date_callback ডিফাইন আছে কিনা
if "async def apt_date_callback" not in content:
    print("⏩ apt_date_callback যোগ করা হচ্ছে...")
    # _date_multi_keyboard ফাংশনের পরে যোগ করি
    insert_after = "def _date_multi_keyboard(selected: set) -> InlineKeyboardMarkup:"
    if insert_after in content:
        new_func = '''

async def apt_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    date_str = query.data.replace("aptdate_", "")
    selected = context.user_data.setdefault("apt_selected_dates", set())
    if date_str in selected:
        selected.discard(date_str)
    else:
        selected.add(date_str)
    await query.edit_message_reply_markup(reply_markup=_date_multi_keyboard(selected))
    return APT_DATE
'''
        content = content.replace(insert_after, insert_after + new_func, 1)
        print("✅ apt_date_callback যোগ করা হয়েছে")
    else:
        print("❌ _date_multi_keyboard খুঁজে পাওয়া যায়নি")
else:
    print("⏩ apt_date_callback ইতিমধ্যে আছে")

# 2. main() এ APT_DATE স্টেটে CallbackQueryHandler রেজিস্টার আছে কিনা
if "CallbackQueryHandler(apt_date_callback, pattern=\"^aptdate_\")" not in content:
    print("⏩ APT_DATE হ্যান্ডলারে CallbackQueryHandler যোগ করা হচ্ছে...")
    # APT_DATE স্টেট খুঁজি
    apt_date_state = re.search(r'APT_DATE:\s*\[(.*?)\]', content, re.DOTALL)
    if apt_date_state:
        old_block = apt_date_state.group(0)
        # নতুন হ্যান্ডলার যোগ
        new_block = old_block.replace(
            'APT_DATE: [',
            'APT_DATE: [\n                CallbackQueryHandler(apt_date_callback, pattern="^aptdate_"),'
        )
        content = content.replace(old_block, new_block, 1)
        print("✅ CallbackQueryHandler যোগ করা হয়েছে")
    else:
        print("❌ APT_DATE স্টেট খুঁজে পাওয়া যায়নি")
else:
    print("⏩ CallbackQueryHandler ইতিমধ্যে আছে")

# 3. apt_date_done_callback ডিফাইন আছে কিনা (যদি না থাকে)
if "async def apt_date_done_callback" not in content:
    print("⏩ apt_date_done_callback যোগ করা হচ্ছে...")
    insert_after = "async def apt_date_callback"
    if insert_after in content:
        new_func = '''

async def apt_date_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected = context.user_data.get("apt_selected_dates", set())
    if not selected:
        await query.answer("কমপক্ষে ১টা দিন বাছাই করো।", show_alert=True)
        return APT_DATE
    await query.answer()
    await query.edit_message_text(f"✅ {len(selected)}টি দিন বাছাই করা হয়েছে।")
    await query.message.reply_text(
        "এই দিনগুলো কি প্রতি সপ্তাহে repeat হবে?", reply_markup=_repeat_keyboard()
    )
    return APT_REPEAT
'''
        content = content.replace(insert_after, insert_after + new_func, 1)
        print("✅ apt_date_done_callback যোগ করা হয়েছে")
    else:
        print("❌ apt_date_callback খুঁজে পাওয়া যায়নি")
else:
    print("⏩ apt_date_done_callback ইতিমধ্যে আছে")

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

try:
    compile(content, "bot.py", "exec")
    print("✅ সিনট্যাক্স ঠিক আছে")
except SyntaxError as e:
    print(f"❌ সিনট্যাক্স এরর: {e}")

