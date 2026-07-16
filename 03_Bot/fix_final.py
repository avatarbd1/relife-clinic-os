#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. apt_date_callback ডিফাইন নেই? যোগ করি
if "async def apt_date_callback" not in content:
    print("⏩ apt_date_callback যোগ করা হচ্ছে...")
    insert_point = "def _date_multi_keyboard"
    if insert_point in content:
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
        content = content.replace(insert_point, insert_point + new_func, 1)
        print("✅ apt_date_callback যোগ হয়েছে")

# 2. apt_date_done_callback ডিফাইন নেই? যোগ করি
if "async def apt_date_done_callback" not in content:
    print("⏩ apt_date_done_callback যোগ করা হচ্ছে...")
    insert_point = "async def apt_date_callback"
    if insert_point in content:
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
        content = content.replace(insert_point, insert_point + new_func, 1)
        print("✅ apt_date_done_callback যোগ হয়েছে")

# 3. apt_repeat_callback ডিফাইন নেই? যোগ করি
if "async def apt_repeat_callback" not in content:
    print("⏩ apt_repeat_callback যোগ করা হচ্ছে...")
    insert_point = "async def apt_date_done_callback"
    if insert_point in content:
        new_func = '''

async def apt_repeat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    weeks = int(query.data.replace("aptrepeat_", ""))
    base_dates = context.user_data.get("apt_selected_dates", set())
    all_dates = set(base_dates)
    for base in base_dates:
        base_dt = datetime.strptime(base, "%Y-%m-%d")
        for w in range(1, weeks + 1):
            all_dates.add((base_dt + timedelta(weeks=w)).strftime("%Y-%m-%d"))
    dates_sorted = sorted(all_dates)
    context.user_data.setdefault("new_appointment", {})["Dates"] = dates_sorted
    await query.edit_message_text(f"✅ মোট {len(dates_sorted)}টি তারিখ বাছাই হলো।")
    await query.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো):", reply_markup=_time_keyboard()
    )
    return APT_TIME
'''
        content = content.replace(insert_point, insert_point + new_func, 1)
        print("✅ apt_repeat_callback যোগ হয়েছে")

# 4. APT_DATE স্টেটে CallbackQueryHandler যোগ করি (যদি না থাকে)
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
        print("✅ CallbackQueryHandler যোগ হয়েছে")
    else:
        print("❌ APT_DATE স্টেট খুঁজে পাওয়া যায়নি")

# 5. APT_DATE স্টেটে apt_date_done_callback যোগ করি
if "CallbackQueryHandler(apt_date_done_callback, pattern=\"^aptdatedone_\")" not in content:
    print("⏩ APT_DATE স্টেটে apt_date_done_callback যোগ করা হচ্ছে...")
    # APT_DATE স্টেট খুঁজি
    apt_date_state = re.search(r'APT_DATE:\s*\[(.*?)\]', content, re.DOTALL)
    if apt_date_state:
        old_block = apt_date_state.group(0)
        # নতুন হ্যান্ডলার যোগ
        new_block = old_block.replace(
            'APT_DATE: [',
            'APT_DATE: [\n                CallbackQueryHandler(apt_date_done_callback, pattern="^aptdatedone_"),'
        )
        content = content.replace(old_block, new_block, 1)
        print("✅ apt_date_done_callback হ্যান্ডলার যোগ হয়েছে")

# 6. APT_REPEAT স্টেটে apt_repeat_callback যোগ করি
if "CallbackQueryHandler(apt_repeat_callback, pattern=\"^aptrepeat_\")" not in content:
    print("⏩ APT_REPEAT স্টেটে apt_repeat_callback যোগ করা হচ্ছে...")
    apt_repeat_state = re.search(r'APT_REPEAT:\s*\[(.*?)\]', content, re.DOTALL)
    if apt_repeat_state:
        old_block = apt_repeat_state.group(0)
        new_block = old_block.replace(
            'APT_REPEAT: [',
            'APT_REPEAT: [\n                CallbackQueryHandler(apt_repeat_callback, pattern="^aptrepeat_"),'
        )
        content = content.replace(old_block, new_block, 1)
        print("✅ apt_repeat_callback হ্যান্ডলার যোগ হয়েছে")
    else:
        print("⚠️ APT_REPEAT স্টেট পাওয়া যায়নি (হয়তো পরে যোগ হবে)")

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

try:
    compile(content, "bot.py", "exec")
    print("✅ সিনট্যাক্স ঠিক আছে")
except SyntaxError as e:
    print(f"❌ সিনট্যাক্স এরর: {e}")

