# -*- coding: utf-8 -*-
"""
Patch 3: বুকিং ফ্লো-র প্রতিটা ধাপে "⬅️ আগের ধাপ" ব্যাক বাটন যোগ করা।
- Appointment booking: তারিখ → সময় → থেরাপিস্ট (প্রতি ধাপ থেকে আগের ধাপে ফেরা যাবে)
- Treatment Note: মেশিন সিলেকশন থেকে রোগী-খোঁজার ধাপে ফেরা যাবে
Database/Sheets structure বা business logic কিছুই বদলায় না, শুধু navigation বাটন।
"""
import sys

PATH = "bot.py"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

original_src = src


def apply(label, old, new):
    global src
    count = src.count(old)
    if count != 1:
        print(f"❌ ব্যর্থ: '{label}' অংশটি {count} বার পাওয়া গেছে (আশা করা হয়েছিল ঠিক ১ বার)।")
        print("ফাইলটি অপরিবর্তিত রাখা হলো, কিছু সেভ করা হয়নি।")
        sys.exit(1)
    src = src.replace(old, new, 1)
    print(f"✅ প্রয়োগ হয়েছে: {label}")


# ---------------------------------------------------------------------------
# ১) _machine_keyboard() — মেশিন সিলেকশনে ব্যাক বাটন
# ---------------------------------------------------------------------------
apply(
    "মেশিন কীবোর্ডে ব্যাক বাটন",
    '''    buttons.append([InlineKeyboardButton("✅ সম্পন্ন — সেভ করো", callback_data="trdone_save")])
    buttons.append([InlineKeyboardButton("❌ বাতিল", callback_data="trcancel_")])
    return InlineKeyboardMarkup(buttons)''',
    '''    buttons.append([InlineKeyboardButton("✅ সম্পন্ন — সেভ করো", callback_data="trdone_save")])
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="trback_search")])
    buttons.append([InlineKeyboardButton("❌ বাতিল", callback_data="trcancel_")])
    return InlineKeyboardMarkup(buttons)''',
)

# ---------------------------------------------------------------------------
# ২) _date_multi_keyboard() — তারিখ-নির্বাচনে ব্যাক বাটন (রোগী-খোঁজার ধাপে ফেরত)
# ---------------------------------------------------------------------------
apply(
    "তারিখ কীবোর্ডে ব্যাক বাটন",
    '''    buttons.append([InlineKeyboardButton(done_label, callback_data="aptdatedone")])
    return InlineKeyboardMarkup(buttons)


def _date_keyboard() -> InlineKeyboardMarkup:''',
    '''    buttons.append([InlineKeyboardButton(done_label, callback_data="aptdatedone")])
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="aptback_search")])
    return InlineKeyboardMarkup(buttons)


def _date_keyboard() -> InlineKeyboardMarkup:''',
)

# ---------------------------------------------------------------------------
# ৩) _time_keyboard() — সময়-নির্বাচনে ব্যাক বাটন (তারিখ-নির্বাচনের ধাপে ফেরত)
# ---------------------------------------------------------------------------
apply(
    "সময় কীবোর্ডে ব্যাক বাটন",
    '''    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def _therapist_keyboard() -> InlineKeyboardMarkup:''',
    '''    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="aptback_date")])
    return InlineKeyboardMarkup(buttons)


def _therapist_keyboard() -> InlineKeyboardMarkup:''',
)

# ---------------------------------------------------------------------------
# ৪) _therapist_keyboard() — থেরাপিস্ট-নির্বাচনে ব্যাক বাটন (সময়-নির্বাচনের ধাপে ফেরত)
# ---------------------------------------------------------------------------
apply(
    "থেরাপিস্ট কীবোর্ডে ব্যাক বাটন",
    '''def _therapist_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"aptther_{name}")]
        for name in THERAPIST_NAMES
    ]
    return InlineKeyboardMarkup(buttons)''',
    '''def _therapist_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(name, callback_data=f"aptther_{name}")]
        for name in THERAPIST_NAMES
    ]
    buttons.append([InlineKeyboardButton("⬅️ আগের ধাপ", callback_data="aptback_time")])
    return InlineKeyboardMarkup(buttons)''',
)

# ---------------------------------------------------------------------------
# ৫) apt_back_to_search_callback — নতুন ফাংশন (apt_select_callback-এর পরে বসানো)
# ---------------------------------------------------------------------------
apply(
    "apt_back_to_search_callback ফাংশন যোগ",
    '''    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text(
        "তারিখ বেছে নাও — একাধিক দিনও বাছাই করা যাবে (একাধিকবার চাপো), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_date_multi_keyboard(set()),
    )
    return APT_DATE


async def apt_select(update: Update, context: ContextTypes.DEFAULT_TYPE):''',
    '''    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})"
    )
    await query.message.reply_text(
        "তারিখ বেছে নাও — একাধিক দিনও বাছাই করা যাবে (একাধিকবার চাপো), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_date_multi_keyboard(set()),
    )
    return APT_DATE


async def apt_back_to_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """তারিখ-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার রোগী খোঁজার ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("apt_dates", None)
    context.user_data.pop("new_appointment", None)
    await query.edit_message_text(
        "⬅️ রোগী খোঁজার ধাপে ফিরে যাওয়া হলো।\nরোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):"
    )
    recent_kb = _recent_patient_buttons("aptsel_")
    if recent_kb:
        await query.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return APT_SEARCH


async def apt_select(update: Update, context: ContextTypes.DEFAULT_TYPE):''',
)

# ---------------------------------------------------------------------------
# ৬) apt_back_to_date_callback — নতুন ফাংশন (apt_date_done_callback-এর পরে বসানো)
# ---------------------------------------------------------------------------
apply(
    "apt_back_to_date_callback ফাংশন যোগ",
    '''    await query.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো) — সবগুলো দিনের জন্য একই সময় প্রযোজ্য হবে:",
        reply_markup=_time_keyboard(),
    )
    return APT_TIME


async def apt_date(update: Update, context: ContextTypes.DEFAULT_TYPE):''',
    '''    await query.message.reply_text(
        "সময় বেছে নাও (অথবা টাইপ করো) — সবগুলো দিনের জন্য একই সময় প্রযোজ্য হবে:",
        reply_markup=_time_keyboard(),
    )
    return APT_TIME


async def apt_back_to_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """সময়-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার তারিখ-নির্বাচনের ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    a = context.user_data.setdefault("new_appointment", {})
    prev_dates = set(a.get("Dates") or ([a["Date"]] if a.get("Date") else []))
    context.user_data["apt_dates"] = prev_dates
    await query.edit_message_text(
        "⬅️ তারিখ বেছে নাও — একাধিক দিনও বাছাই করা যাবে (একাধিকবার চাপো), তারপর 'পরের ধাপ' চাপো:",
        reply_markup=_date_multi_keyboard(prev_dates),
    )
    return APT_DATE


async def apt_date(update: Update, context: ContextTypes.DEFAULT_TYPE):''',
)

# ---------------------------------------------------------------------------
# ৭) apt_back_to_time_callback — নতুন ফাংশন (apt_time-এর পরে বসানো)
# ---------------------------------------------------------------------------
apply(
    "apt_back_to_time_callback ফাংশন যোগ",
    '''    await update.message.reply_text(
        "থেরাপিস্ট বেছে নাও (অথবা টাইপ করো):",
        reply_markup=_therapist_keyboard(),
    )
    return APT_THERAPIST


def _apt_summary_text(a: dict) -> str:''',
    '''    await update.message.reply_text(
        "থেরাপিস্ট বেছে নাও (অথবা টাইপ করো):",
        reply_markup=_therapist_keyboard(),
    )
    return APT_THERAPIST


async def apt_back_to_time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """থেরাপিস্ট-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার সময়-নির্বাচনের ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⬅️ সময় বেছে নাও (অথবা টাইপ করো) — সবগুলো দিনের জন্য একই সময় প্রযোজ্য হবে:",
        reply_markup=_time_keyboard(),
    )
    return APT_TIME


def _apt_summary_text(a: dict) -> str:''',
)

# ---------------------------------------------------------------------------
# ৮) treat_back_to_search_callback — নতুন ফাংশন (treat_select_callback-এর পরে বসানো)
# ---------------------------------------------------------------------------
apply(
    "treat_back_to_search_callback ফাংশন যোগ",
    '''    await query.edit_message_text(summary, reply_markup=_machine_keyboard(selected))
    return TREAT_MACHINES


async def treat_machine_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):''',
    '''    await query.edit_message_text(summary, reply_markup=_machine_keyboard(selected))
    return TREAT_MACHINES


async def treat_back_to_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """মেশিন-নির্বাচনের ধাপ থেকে '⬅️ আগের ধাপ' চাপলে আবার রোগী খোঁজার ধাপে ফিরে যায়।"""
    query = update.callback_query
    await query.answer()
    context.user_data.pop("treatment", None)
    context.user_data.pop("treat_selected", None)
    await query.edit_message_text(
        "⬅️ রোগী খোঁজার ধাপে ফিরে যাওয়া হলো।\nরোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):"
    )
    recent_kb = _recent_patient_buttons("treatsel_")
    if recent_kb:
        await query.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return TREAT_SEARCH


async def treat_machine_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):''',
)

# ---------------------------------------------------------------------------
# ৯) conversation states-এ নতুন callback হ্যান্ডলার wire করা
# ---------------------------------------------------------------------------
apply(
    "APT_DATE state-এ ব্যাক হ্যান্ডলার যোগ",
    '''            APT_DATE: [
                CallbackQueryHandler(apt_date_toggle_callback, pattern="^aptdatetoggle_"),
                CallbackQueryHandler(apt_date_done_callback, pattern="^aptdatedone$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_date),
            ],''',
    '''            APT_DATE: [
                CallbackQueryHandler(apt_date_toggle_callback, pattern="^aptdatetoggle_"),
                CallbackQueryHandler(apt_date_done_callback, pattern="^aptdatedone$"),
                CallbackQueryHandler(apt_back_to_search_callback, pattern="^aptback_search$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_date),
            ],''',
)

apply(
    "APT_TIME state-এ ব্যাক হ্যান্ডলার যোগ",
    '''            APT_TIME: [
                CallbackQueryHandler(apt_time_callback, pattern="^apttime_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_time),
            ],''',
    '''            APT_TIME: [
                CallbackQueryHandler(apt_time_callback, pattern="^apttime_"),
                CallbackQueryHandler(apt_back_to_date_callback, pattern="^aptback_date$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_time),
            ],''',
)

apply(
    "APT_THERAPIST state-এ ব্যাক হ্যান্ডলার যোগ",
    '''            APT_THERAPIST: [
                CallbackQueryHandler(apt_therapist_callback, pattern="^aptther_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_therapist),
            ],''',
    '''            APT_THERAPIST: [
                CallbackQueryHandler(apt_therapist_callback, pattern="^aptther_"),
                CallbackQueryHandler(apt_back_to_time_callback, pattern="^aptback_time$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_therapist),
            ],''',
)

apply(
    "TREAT_MACHINES state-এ ব্যাক হ্যান্ডলার যোগ",
    '''            TREAT_MACHINES: [
                CallbackQueryHandler(treat_machine_toggle, pattern="^trm_"),
                CallbackQueryHandler(treat_machine_done, pattern="^trdone_"),
                CallbackQueryHandler(treat_machine_cancel_callback, pattern="^trcancel_"),
            ],''',
    '''            TREAT_MACHINES: [
                CallbackQueryHandler(treat_machine_toggle, pattern="^trm_"),
                CallbackQueryHandler(treat_machine_done, pattern="^trdone_"),
                CallbackQueryHandler(treat_back_to_search_callback, pattern="^trback_search$"),
                CallbackQueryHandler(treat_machine_cancel_callback, pattern="^trcancel_"),
            ],''',
)

# ---------------------------------------------------------------------------
if src == original_src:
    print("❌ কিছুই বদলায়নি, থেমে গেলাম।")
    sys.exit(1)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("\n🎉 Patch 3 সফলভাবে প্রয়োগ করা হয়েছে — bot.py আপডেট হয়েছে।")
print("এখন: python -m py_compile bot.py  দিয়ে সিনট্যাক্স চেক করে নাও, তারপর কমিট/পুশ করো।")
