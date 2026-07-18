#!/usr/bin/env python3
"""
Patch 2 — Relife Clinic OS bot.py  (apply AFTER Patch 1)
- New shared helper _patient_search_buttons() merges the 6 duplicated
  search-result keyboard loops (apt/pay/treat/tplan/thist/hist).
- Every search-result screen now has a "🔙 বাতিল করো" button — no more
  typing /cancel to escape a search screen.
- main() wiring updated so the new back-buttons are registered in every
  relevant conversation state.

Run from the folder containing bot.py:
    python patch2.py
"""
import sys

PATH = "bot.py"

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

original_src = src


def replace_once(old, new, label):
    global src
    count = src.count(old)
    if count == 0:
        print(f"❌ FAILED to locate block for: {label}")
        print("   (bot.py may already be patched, or has changed since this patch was written)")
        sys.exit(1)
    if count > 1:
        print(f"❌ Block for '{label}' is not unique ({count} matches) — aborting to avoid a bad edit.")
        sys.exit(1)
    src = src.replace(old, new, 1)
    print(f"✅ applied: {label}")


# ---------------------------------------------------------------------------
# 1) New shared helper: _patient_search_buttons() + 6 tiny "answer + cancel"
#    wrapper callbacks, placed right after _recent_patient_buttons().
# ---------------------------------------------------------------------------
replace_once(
    old='''def _date_multi_keyboard(selected: set) -> InlineKeyboardMarkup:''',
    new='''def _patient_search_buttons(results, prefix: str, cancel_data: str) -> InlineKeyboardMarkup:
    """সার্চ-রেজাল্ট থেকে রোগী বাছাইয়ের বাটন বানায় (নাম বাটন + শেষে 🔙 বাতিল বাটন)।
    আগে apt/pay/treat/tplan/thist/hist প্রতিটাতে এই একই লুপ আলাদা আলাদা কপি-পেস্ট করা ছিল।"""
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name') or p.get('Name') or 'Unknown'} ({p.get('Patient_ID', '')})",
            callback_data=f"{prefix}{p.get('Patient_ID', '')}",
        )]
        for p in results
    ]
    buttons.append([InlineKeyboardButton("🔙 বাতিল করো", callback_data=cancel_data)])
    return InlineKeyboardMarkup(buttons)


async def _apt_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await apt_cancel(update, context)


async def _pay_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await pay_cancel(update, context)


async def _treat_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await treat_cancel(update, context)


async def _tplan_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await tplan_cancel(update, context)


async def _hist_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await hist_cancel(update, context)


async def _thist_search_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    return await thist_cancel(update, context)


def _date_multi_keyboard(selected: set) -> InlineKeyboardMarkup:''',
    label="add _patient_search_buttons() + 6 cancel wrappers",
)

# ---------------------------------------------------------------------------
# 2) apt_search — use shared helper + Back button
# ---------------------------------------------------------------------------
replace_once(
    old='''    results = results[:10]
    context.user_data["apt_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"aptsel_{p.get('Patient_ID')}",
        )]
        for p in results
    ]
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return APT_SELECT''',
    new='''    results = results[:10]
    context.user_data["apt_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=_patient_search_buttons(results, "aptsel_", "aptsearchback"),
    )
    return APT_SELECT''',
    label="apt_search: shared helper + Back button",
)

# ---------------------------------------------------------------------------
# 3) pay_search
# ---------------------------------------------------------------------------
replace_once(
    old='''    results = results[:10]
    context.user_data["pay_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"paysel_{p.get('Patient_ID')}",
        )]
        for p in results
    ]
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return PAY_SELECT''',
    new='''    results = results[:10]
    context.user_data["pay_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=_patient_search_buttons(results, "paysel_", "paysearchback"),
    )
    return PAY_SELECT''',
    label="pay_search: shared helper + Back button",
)

# ---------------------------------------------------------------------------
# 4) treat_search
# ---------------------------------------------------------------------------
replace_once(
    old='''    results = results[:10]
    context.user_data["treat_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"treatsel_{p.get('Patient_ID')}",
        )]
        for p in results
    ]
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return TREAT_SELECT''',
    new='''    results = results[:10]
    context.user_data["treat_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=_patient_search_buttons(results, "treatsel_", "treatsearchback"),
    )
    return TREAT_SELECT''',
    label="treat_search: shared helper + Back button",
)

# ---------------------------------------------------------------------------
# 5) tplan_search
# ---------------------------------------------------------------------------
replace_once(
    old='''    results = results[:10]
    context.user_data["tplan_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    buttons = [
        [InlineKeyboardButton(
            f"{p.get('Full_Name')} ({p.get('Patient_ID')})",
            callback_data=f"tplansel_{p.get('Patient_ID')}",
        )]
        for p in results
    ]
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return TPLAN_SELECT''',
    new='''    results = results[:10]
    context.user_data["tplan_search_results"] = {
        p.get("Patient_ID", "").strip(): p for p in results
    }
    await update.message.reply_text(
        "🔍 নিচের তালিকা থেকে রোগী বেছে নাও:",
        reply_markup=_patient_search_buttons(results, "tplansel_", "tplansearchback"),
    )
    return TPLAN_SELECT''',
    label="tplan_search: shared helper + Back button",
)

# ---------------------------------------------------------------------------
# 6) thist_search
# ---------------------------------------------------------------------------
replace_once(
    old='''    buttons = []
    for p in results[:10]:
        pid = p.get("Patient_ID", "")
        name = p.get("Full_Name") or p.get("Name") or "Unknown"
        buttons.append([InlineKeyboardButton(f"{name} ({pid})", callback_data=f"thpsel_{pid}")])
    await update.message.reply_text(
        "কোন রোগীর ট্রিটমেন্ট হিস্টরি দেখতে চাও?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return "THIST_SEARCH"''',
    new='''    results = results[:10]
    await update.message.reply_text(
        "কোন রোগীর ট্রিটমেন্ট হিস্টরি দেখতে চাও?",
        reply_markup=_patient_search_buttons(results, "thpsel_", "thistsearchback"),
    )
    return "THIST_SEARCH"''',
    label="thist_search: shared helper + Back button",
)

# ---------------------------------------------------------------------------
# 7) hist_search
# ---------------------------------------------------------------------------
replace_once(
    old='''    buttons = []
    for p in results[:10]:
        pid = p.get("Patient_ID", "")
        name = p.get("Full_Name") or p.get("Name") or "Unknown"
        buttons.append([InlineKeyboardButton(f"{name} ({pid})", callback_data=f"histsel_{pid}")])
    await update.message.reply_text(
        "কোন রোগী দেখতে চাও?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return "HIST_SEARCH"''',
    new='''    results = results[:10]
    await update.message.reply_text(
        "কোন রোগী দেখতে চাও?",
        reply_markup=_patient_search_buttons(results, "histsel_", "histsearchback"),
    )
    return "HIST_SEARCH"''',
    label="hist_search: shared helper + Back button",
)

# ---------------------------------------------------------------------------
# 8) main() wiring — register the new Back buttons in every relevant state.
# ---------------------------------------------------------------------------
replace_once(
    old='''            APT_SEARCH: [
                CallbackQueryHandler(apt_select_callback, pattern="^aptsel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_search),
            ],
            APT_SELECT: [
                CallbackQueryHandler(apt_select_callback, pattern="^aptsel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_select),
            ],''',
    new='''            APT_SEARCH: [
                CallbackQueryHandler(apt_select_callback, pattern="^aptsel_"),
                CallbackQueryHandler(_apt_search_cancel, pattern="^aptsearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_search),
            ],
            APT_SELECT: [
                CallbackQueryHandler(apt_select_callback, pattern="^aptsel_"),
                CallbackQueryHandler(_apt_search_cancel, pattern="^aptsearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), apt_select),
            ],''',
    label="main(): wire aptsearchback into apt_conv",
)

replace_once(
    old='''            PAY_SEARCH: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_search),
            ],
            PAY_SELECT: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_select),
            ],''',
    new='''            PAY_SEARCH: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                CallbackQueryHandler(_pay_search_cancel, pattern="^paysearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_search),
            ],
            PAY_SELECT: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                CallbackQueryHandler(_pay_search_cancel, pattern="^paysearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_select),
            ],''',
    label="main(): wire paysearchback into pay_conv",
)

replace_once(
    old='''            TREAT_SEARCH: [
                CallbackQueryHandler(treat_select_callback, pattern="^treatsel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_search),
            ],
            TREAT_SELECT: [CallbackQueryHandler(treat_select_callback, pattern="^treatsel_")],''',
    new='''            TREAT_SEARCH: [
                CallbackQueryHandler(treat_select_callback, pattern="^treatsel_"),
                CallbackQueryHandler(_treat_search_cancel, pattern="^treatsearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), treat_search),
            ],
            TREAT_SELECT: [
                CallbackQueryHandler(treat_select_callback, pattern="^treatsel_"),
                CallbackQueryHandler(_treat_search_cancel, pattern="^treatsearchback$"),
            ],''',
    label="main(): wire treatsearchback into treat_conv",
)

replace_once(
    old='''            TPLAN_SEARCH: [
                CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_search),
            ],
            TPLAN_SELECT: [CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_")],''',
    new='''            TPLAN_SEARCH: [
                CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_"),
                CallbackQueryHandler(_tplan_search_cancel, pattern="^tplansearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_search),
            ],
            TPLAN_SELECT: [
                CallbackQueryHandler(tplan_select_callback, pattern="^tplansel_"),
                CallbackQueryHandler(_tplan_search_cancel, pattern="^tplansearchback$"),
            ],''',
    label="main(): wire tplansearchback into tplan_conv",
)

replace_once(
    old='''            "HIST_SEARCH": [
                CallbackQueryHandler(hist_select_callback, pattern="^histsel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), hist_search),
            ],''',
    new='''            "HIST_SEARCH": [
                CallbackQueryHandler(hist_select_callback, pattern="^histsel_"),
                CallbackQueryHandler(_hist_search_cancel, pattern="^histsearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), hist_search),
            ],''',
    label="main(): wire histsearchback into hist_conv",
)

replace_once(
    old='''            "THIST_SEARCH": [
                CallbackQueryHandler(thist_patient_callback, pattern="^thpsel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, thist_search),
            ],''',
    new='''            "THIST_SEARCH": [
                CallbackQueryHandler(thist_patient_callback, pattern="^thpsel_"),
                CallbackQueryHandler(_thist_search_cancel, pattern="^thistsearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, thist_search),
            ],''',
    label="main(): wire thistsearchback into thist_conv",
)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("\n🎉 Patch 2 applied successfully to bot.py")
print(f"   {len(original_src)} -> {len(src)} bytes")
