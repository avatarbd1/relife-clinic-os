#!/usr/bin/env python3
import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# চেক করে দেখি ফাংশনগুলো ইতিমধ্যে আছে কিনা
if "async def apt_date_done_callback" in content:
    print("✅ apt_date_done_callback ইতিমধ্যে আছে, কিছু করব না।")
else:
    # apt_date_callback ফাংশনের শেষে (return APT_DATE এর পর) নতুন ফাংশন যোগ করি
    # আমরা একটি অ্যাঙ্কর হিসেবে "return APT_DATE" ব্যবহার করি, কিন্তু সেটি একাধিকবার থাকতে পারে।
    # আমরা apt_date_callback ফাংশনের শেষ return টার্গেট করি।
    # প্রথমে apt_date_callback ফাংশনের পুরো ব্লক খুঁজি
    pattern = r'(async def apt_date_callback\([^)]*\):.*?return APT_DATE)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print("❌ apt_date_callback ফাংশন খুঁজে পাওয়া যায়নি।")
        exit(1)
    old_block = match.group(1)
    # নতুন ফাংশনগুলো প্রস্তুত
    new_functions = '''

async def apt_date_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    selected = context.user_data.get("apt_selected_dates", set())
    if not selected:
        await query.answer("কমপক্ষে ১টা দিন বাছাই করো।", show_alert=True)
        return APT_DATE
    await query.answer()
    await query.edit_message_text(f"✅ {len(selected)}টি দিন বাছাই করা হয়েছে।")
    await query.message.reply_text(
        "এই দিনগুলো কি প্রতি সপ্তাহে repeat হবে?", reply_markup=_repeat_keyboard()
    )
    return APT_REPEAT


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
    # পুরনো ব্লকে নতুন ফাংশন যোগ করি (return APT_DATE এর পর)
    new_block = old_block + new_functions
    content = content.replace(old_block, new_block, 1)
    with open("bot.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ apt_date_done_callback ও apt_repeat_callback যোগ করা হয়েছে।")

# সিনট্যাক্স চেক
try:
    compile(open("bot.py", "r", encoding="utf-8").read(), "bot.py", "exec")
    print("✅ সিনট্যাক্স ঠিক আছে।")
except SyntaxError as e:
    print(f"❌ সিনট্যাক্স এরর: {e}")

