"""
patch_therapist_buttons.py
অ্যাপয়েন্টমেন্ট বুকিং-এ থেরাপিস্টের নাম টাইপ করার বদলে বাটন (Nipa / Saiful) যোগ করে।
03_Bot/ ফোল্ডারে রেখে চালাও: python patch_therapist_buttons.py
"""

import shutil
import sys

BOT_FILE = "bot.py"


def backup(path):
    bak = path + ".bak2"
    shutil.copy(path, bak)
    print(f"✅ Backup নেওয়া হলো: {bak}")


def apply_replace(content, old, new, label):
    count = content.count(old)
    if count != 1:
        print(f"❌ ব্যর্থ: '{label}' — {count} বার মিলেছে (দরকার ছিল ঠিক ১ বার)।")
        print("   হয়তো ফাইলটা আগেই পরিবর্তিত, অথবা কোড ভিন্ন। ম্যানুয়ালি চেক করো।")
        sys.exit(1)
    print(f"✅ প্রয়োগ হলো: {label}")
    return content.replace(old, new)


with open(BOT_FILE, "r", encoding="utf-8") as f:
    bot_content = f.read()

backup(BOT_FILE)

bot_content = apply_replace(
    bot_content,
    'PAY_METHODS = ["Cash", "bKash", "Nagad", "Card"]\n',
    'PAY_METHODS = ["Cash", "bKash", "Nagad", "Card"]\n'
    'THERAPIST_NAMES = ["Nipa", "Saiful"]\n',
    "THERAPIST_NAMES লিস্ট যোগ",
)

bot_content = apply_replace(
    bot_content,
    "def _payment_method_keyboard() -> ReplyKeyboardMarkup:",
    "def _therapist_keyboard() -> InlineKeyboardMarkup:\n"
    "    buttons = [\n"
    "        [InlineKeyboardButton(name, callback_data=f\"aptther_{name}\")]\n"
    "        for name in THERAPIST_NAMES\n"
    "    ]\n"
    "    return InlineKeyboardMarkup(buttons)\n"
    "\n\n"
    "def _payment_method_keyboard() -> ReplyKeyboardMarkup:",
    "_therapist_keyboard() ফাংশন যোগ",
)

bot_content = apply_replace(
    bot_content,
    '    await query.edit_message_text(f"✅ সময় নির্বাচন করা হয়েছে: {time_str}")\n'
    '    await query.message.reply_text("থেরাপিস্ট / ডাক্তারের নাম লেখো:")\n'
    "    return APT_THERAPIST",
    '    await query.edit_message_text(f"✅ সময় নির্বাচন করা হয়েছে: {time_str}")\n'
    "    await query.message.reply_text(\n"
    '        "থেরাপিস্ট বেছে নাও (অথবা টাইপ করো):",\n'
    "        reply_markup=_therapist_keyboard(),\n"
    "    )\n"
    "    return APT_THERAPIST",
    "apt_time_callback-এ থেরাপিস্ট বাটন যোগ",
)

bot_content = apply_replace(
    bot_content,
    '    context.user_data["new_appointment"]["Time"] = update.message.text.strip()\n'
    '    await update.message.reply_text("থেরাপিস্ট / ডাক্তারের নাম লেখো:")\n'
    "    return APT_THERAPIST",
    '    context.user_data["new_appointment"]["Time"] = update.message.text.strip()\n'
    "    await update.message.reply_text(\n"
    '        "থেরাপিস্ট বেছে নাও (অথবা টাইপ করো):",\n'
    "        reply_markup=_therapist_keyboard(),\n"
    "    )\n"
    "    return APT_THERAPIST",
    "apt_time-এ থেরাপিস্ট বাটন যোগ",
)

OLD_APT_THERAPIST_END = '''async def apt_therapist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Therapist"] = update.message.text.strip()
    a = context.user_data["new_appointment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\\n\\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\\n"
        f"Department: {a['Department']}\\n"
        f"তারিখ: {a['Date']}\\nসময়: {a['Time']}\\n"
        f"থেরাপিস্ট: {a['Therapist']}\\n\\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return APT_CONFIRM'''

NEW_APT_THERAPIST_END = OLD_APT_THERAPIST_END + '''


async def apt_therapist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    therapist_name = query.data.replace("aptther_", "")
    context.user_data["new_appointment"]["Therapist"] = therapist_name
    a = context.user_data["new_appointment"]
    summary = (
        "নিচের তথ্য ঠিক আছে কিনা চেক করো:\\n\\n"
        f"রোগী: {a['Patient_Name']} ({a['Patient_ID']})\\n"
        f"Department: {a['Department']}\\n"
        f"তারিখ: {a['Date']}\\nসময়: {a['Time']}\\n"
        f"থেরাপিস্ট: {a['Therapist']}\\n\\n"
        "ঠিক থাকলে নিচের বাটনে ট্যাপ করো।"
    )
    confirm_keyboard = ReplyKeyboardMarkup(
        [["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True
    )
    await query.edit_message_text(f"✅ থেরাপিস্ট নির্বাচন করা হয়েছে: {therapist_name}")
    await query.message.reply_text(summary, reply_markup=confirm_keyboard)
    return APT_CONFIRM'''

bot_content = apply_replace(
    bot_content,
    OLD_APT_THERAPIST_END,
    NEW_APT_THERAPIST_END,
    "apt_therapist_callback ফাংশন যোগ",
)

bot_content = apply_replace(
    bot_content,
    "            APT_THERAPIST: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_therapist)],\n",
    "            APT_THERAPIST: [\n"
    '                CallbackQueryHandler(apt_therapist_callback, pattern="^aptther_"),\n'
    "                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_therapist),\n"
    "            ],\n",
    "APT_THERAPIST state-এ callback হ্যান্ডলার যোগ",
)

with open(BOT_FILE, "w", encoding="utf-8") as f:
    f.write(bot_content)

print(f"✅ {BOT_FILE} সেভ হয়েছে।\n")
print("🎉 প্যাচ সম্পূর্ণ! এখন 'python3 -m py_compile bot.py' দিয়ে সিনট্যাক্স চেক করো।")
