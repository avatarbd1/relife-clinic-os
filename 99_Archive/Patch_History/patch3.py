import io

PATH = "bot.py"

with io.open(PATH, encoding="utf-8") as f:
    src = f.read()


def replace_once(src, old, new, label):
    n = src.count(old)
    if n != 1:
        raise SystemExit(
            f"❌ ব্যর্থ — '{label}' ব্লকটি {n} বার পাওয়া গেছে (আশা করা হয়েছিল ঠিক ১ বার)।\n"
            "bot.py সম্ভবত পরিবর্তিত হয়ে গেছে। এই patch চালানো বন্ধ করে স্ক্রিনশট/grep পাঠাও।"
        )
    return src.replace(old, new, 1)


old = '''def _time_keyboard() -> InlineKeyboardMarkup:
    slots = [
        "09:00 AM", "10:00 AM", "11:00 AM",
        "12:00 PM", "01:00 PM",
        "03:00 PM", "04:00 PM", "05:00 PM",
        "06:00 PM", "07:00 PM", "08:00 PM",
    ]
    buttons = []
    row = []
    for s in slots:
        row.append(InlineKeyboardButton(s, callback_data=f"apttime_{s}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)'''
new = '''def _time_keyboard() -> InlineKeyboardMarkup:
    slots = [
        "09:00 AM", "10:00 AM", "11:00 AM",
        "12:00 PM", "01:00 PM",
        "03:00 PM", "04:00 PM", "05:00 PM",
        "06:00 PM", "07:00 PM", "08:00 PM",
    ]
    buttons = []
    row = []
    for s in slots:
        row.append(InlineKeyboardButton(s, callback_data=f"apttime_{s}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ (তারিখ)", callback_data="aptback_date")])
    return InlineKeyboardMarkup(buttons)


def _therapist_back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [["⬅️ আগের ধাপ (সময়)"]], resize_keyboard=True, one_time_keyboard=True
    )


async def apt_back_to_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """সময় বাছাইয়ের ধাপ থেকে 'আগের ধাপ' চাপলে আবার তারিখ বাছাইয়ে ফিরিয়ে নেয়।"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⬅️ তারিখ আবার বেছে নাও:")
    await query.message.reply_text("তারিখ বেছে নাও 👇", reply_markup=_date_keyboard())
    return APT_DATE'''
src = replace_once(src, old, new, "_time_keyboard + নতুন back helper/callback")

old = '''async def apt_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_str = query.data.replace("apttime_", "")
    context.user_data.setdefault("new_appointment", {})["Time"] = time_str
    await query.edit_message_text(f"✅ সময় নির্বাচন করা হয়েছে: {time_str}")
    await query.message.reply_text("থেরাপিস্ট / ডাক্তারের নাম লেখো:")
    return APT_THERAPIST'''
new = '''async def apt_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    time_str = query.data.replace("apttime_", "")
    context.user_data.setdefault("new_appointment", {})["Time"] = time_str
    await query.edit_message_text(f"✅ সময় নির্বাচন করা হয়েছে: {time_str}")
    await query.message.reply_text(
        "থেরাপিস্ট / ডাক্তারের নাম লেখো:", reply_markup=_therapist_back_keyboard()
    )
    return APT_THERAPIST'''
src = replace_once(src, old, new, "apt_time_callback")

old = '''async def apt_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Time"] = update.message.text.strip()
    await update.message.reply_text("থেরাপিস্ট / ডাক্তারের নাম লেখো:")
    return APT_THERAPIST'''
new = '''async def apt_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Time"] = update.message.text.strip()
    await update.message.reply_text(
        "থেরাপিস্ট / ডাক্তারের নাম লেখো:", reply_markup=_therapist_back_keyboard()
    )
    return APT_THERAPIST'''
src = replace_once(src, old, new, "apt_time")

old = '''async def apt_therapist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_appointment"]["Therapist"] = update.message.text.strip()
    a = context.user_data["new_appointment"]'''
new = '''async def apt_therapist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "⬅️ আগের ধাপ (সময়)":
        await update.message.reply_text(
            "সময় আবার বেছে নাও:", reply_markup=_time_keyboard()
        )
        return APT_TIME
    context.user_data["new_appointment"]["Therapist"] = text
    a = context.user_data["new_appointment"]'''
src = replace_once(src, old, new, "apt_therapist")

old = '''            APT_TIME: [
                CallbackQueryHandler(apt_time_callback, pattern="^apttime_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_time),
            ],'''
new = '''            APT_TIME: [
                CallbackQueryHandler(apt_time_callback, pattern="^apttime_"),
                CallbackQueryHandler(apt_back_to_date_callback, pattern="^aptback_date$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_time),
            ],'''
src = replace_once(src, old, new, "apt_conv states (APT_TIME)")

old = '''async def treat_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Exercise"] = "" if text == "-" else text
    await update.message.reply_text("ইলেক্ট্রোথেরাপি মোডালিটি লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard())
    return TREAT_ELECTRO'''
new = '''def _skip_back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["-", "⬅️ আগের ধাপ"]], resize_keyboard=True, one_time_keyboard=True)


async def treat_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Exercise"] = "" if text == "-" else text
    await update.message.reply_text(
        "ইলেক্ট্রোথেরাপি মোডালিটি লেখো (না থাকলে - দাও):", reply_markup=_skip_back_keyboard()
    )
    return TREAT_ELECTRO'''
src = replace_once(src, old, new, "treat_exercise + নতুন _skip_back_keyboard")

old = '''async def treat_electro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Electrotherapy"] = "" if text == "-" else text
    await update.message.reply_text("ম্যানুয়াল থেরাপি টেকনিক লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard())
    return TREAT_MANUAL'''
new = '''async def treat_electro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "⬅️ আগের ধাপ":
        await update.message.reply_text(
            "এক্সারসাইজ প্ল্যান আবার লেখো (না থাকলে - দাও):", reply_markup=_skip_keyboard()
        )
        return TREAT_EXERCISE
    context.user_data["treatment"]["Electrotherapy"] = "" if text == "-" else text
    await update.message.reply_text(
        "ম্যানুয়াল থেরাপি টেকনিক লেখো (না থাকলে - দাও):", reply_markup=_skip_back_keyboard()
    )
    return TREAT_MANUAL'''
src = replace_once(src, old, new, "treat_electro")

old = '''async def treat_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    context.user_data["treatment"]["Manual_Therapy"] = "" if text == "-" else text
    await update.message.reply_text(
        "সেশন নম্বর লেখো (যেমন: 5):",
        reply_markup=_number_keyboard([str(n) for n in range(1, 11)]),
    )
    return TREAT_SESSION'''
new = '''async def treat_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "⬅️ আগের ধাপ":
        await update.message.reply_text(
            "ইলেক্ট্রোথেরাপি মোডালিটি আবার লেখো (না থাকলে - দাও):", reply_markup=_skip_back_keyboard()
        )
        return TREAT_ELECTRO
    context.user_data["treatment"]["Manual_Therapy"] = "" if text == "-" else text
    await update.message.reply_text(
        "সেশন নম্বর লেখো (যেমন: 5):",
        reply_markup=_number_keyboard([str(n) for n in range(1, 11)]),
    )
    return TREAT_SESSION'''
src = replace_once(src, old, new, "treat_manual")

with io.open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("✅ patch3.py সফলভাবে প্রয়োগ হয়েছে — bot.py আপডেট হয়েছে।")
