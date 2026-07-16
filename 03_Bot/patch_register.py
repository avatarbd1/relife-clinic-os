# -*- coding: utf-8 -*-
"""
Daily Register feature patch — bot.py
রান করার আগে ব্যাকআপ নিয়ে নেয় নিজে থেকেই।
"""
import shutil

PATH = "bot.py"
BACKUP = "bot.py.bak_register"

shutil.copy(PATH, BACKUP)
print(f"✅ ব্যাকআপ নেওয়া হয়েছে: {BACKUP}")

with open(PATH, "r", encoding="utf-8") as f:
    src = f.read()

changes = []

def apply(label, old, new, expected=1):
    global src
    count = src.count(old)
    if count != expected:
        changes.append((label, False, count))
        return
    src = src.replace(old, new, expected)
    changes.append((label, True, count))


apply(
    "1) _ALL_MENU_ITEMS-এ MENU_DAILY_REGISTER যোগ",
    '    roles.MENU_PATIENT_LIST,\n]\n_ALL_MENU_REGEX',
    '    roles.MENU_PATIENT_LIST,\n    roles.MENU_DAILY_REGISTER,\n]\n_ALL_MENU_REGEX',
)

apply(
    "2) pay_select_callback আপডেট",
    '''async def pay_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("paysel_", "")
    results = context.user_data.get("pay_search_results", {})
    patient = results.get(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও, তারপর 💳 পেমেন্ট তথ্য চাপো।"
        )
        return ConversationHandler.END
    context.user_data.setdefault("payment", {})["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["payment"]["Department"] = patient.get("Department", "")
    context.user_data.pop("pay_search_results", None)

    total_bill = patient.get("Total_Bill", 0) or 0
    paid_amount = patient.get("Paid_Amount", 0) or 0
    due_amount = patient.get("Due_Amount", 0) or 0
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\\n\\n"
        f"মোট বিল: {total_bill}\\nজমা হয়েছে: {paid_amount}\\nবাকি: {due_amount}"
    )
    await query.message.reply_text(
        "আজ কয়টা সেশন হলো লেখো (না থাকলে 0):",
        reply_markup=_number_keyboard([str(n) for n in range(0, 6)]),
    )
    return PAY_SESSION''',
    '''async def pay_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("paysel_", "")
    results = context.user_data.get("pay_search_results", {})
    patient = results.get(patient_id)
    if not patient:
        await query.edit_message_text(
            "❌ তালিকার মেয়াদ শেষ। আবার শুরু করতে /cancel দাও, তারপর 📋 আজকের রেজিস্টার থেকে ➕ নতুন এন্ট্রি চাপো।"
        )
        return ConversationHandler.END
    context.user_data.setdefault("payment", {})["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["payment"]["Department"] = patient.get("Department", "")
    context.user_data["payment"]["Sessions"] = 1
    context.user_data.pop("pay_search_results", None)

    await query.edit_message_text(
        _register_amount_prompt_text(patient.get("Full_Name", ""), patient.get("Patient_ID", ""), 1),
        reply_markup=_register_amount_keyboard(1),
    )
    return PAY_AMOUNT''',
)

apply(
    "3) pay_select আপডেট",
    '''async def pay_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    results = context.user_data.get("pay_search_results", {})
    patient = results.get(text)
    if not patient:
        await update.message.reply_text(
            "❌ উপরের তালিকা থেকে একটা বাটনে ট্যাপ করো, অথবা /cancel দাও।"
        )
        return PAY_SELECT
    context.user_data["payment"]["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["payment"]["Department"] = patient.get("Department", "")
    context.user_data.pop("pay_search_results", None)

    total_bill = patient.get("Total_Bill", 0) or 0
    paid_amount = patient.get("Paid_Amount", 0) or 0
    due_amount = patient.get("Due_Amount", 0) or 0
    await update.message.reply_text(
        f"রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\\n\\n"
        f"মোট বিল: {total_bill}\\nজমা হয়েছে: {paid_amount}\\nবাকি: {due_amount}\\n\\n"
        "আজ কয়টা সেশন হলো লেখো (না থাকলে 0):"
    )
    return PAY_SESSION''',
    '''async def pay_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    results = context.user_data.get("pay_search_results", {})
    patient = results.get(text)
    if not patient:
        await update.message.reply_text(
            "❌ উপরের তালিকা থেকে একটা বাটনে ট্যাপ করো, অথবা /cancel দাও।"
        )
        return PAY_SELECT
    context.user_data["payment"]["Patient_ID"] = patient.get("Patient_ID", "")
    context.user_data["payment"]["Patient_Name"] = patient.get("Full_Name", "")
    context.user_data["payment"]["Department"] = patient.get("Department", "")
    context.user_data["payment"]["Sessions"] = 1
    context.user_data.pop("pay_search_results", None)

    await update.message.reply_text(
        _register_amount_prompt_text(patient.get("Full_Name", ""), patient.get("Patient_ID", ""), 1),
        reply_markup=_register_amount_keyboard(1),
    )
    return PAY_AMOUNT''',
)

apply(
    "4) plist_action_pay আপডেট",
    '''async def plist_action_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_pay_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["payment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
    }
    total_bill = patient.get("Total_Bill", 0) or 0
    paid_amount = patient.get("Paid_Amount", 0) or 0
    due_amount = patient.get("Due_Amount", 0) or 0
    await query.edit_message_text(
        f"✅ রোগী বাছাই হয়েছে: {patient.get('Full_Name')} ({patient.get('Patient_ID')})\\n\\n"
        f"মোট বিল: {total_bill}\\nজমা হয়েছে: {paid_amount}\\nবাকি: {due_amount}"
    )
    await query.message.reply_text(
        "আজ কয়টা সেশন হলো লেখো (না থাকলে 0):",
        reply_markup=_number_keyboard([str(n) for n in range(0, 6)]),
    )
    return PAY_SESSION''',
    '''async def plist_action_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("plistact_pay_", "")
    patient = sheets.get_patient_by_id(patient_id)
    if not patient:
        await query.edit_message_text("❌ রোগী পাওয়া যায়নি।")
        return ConversationHandler.END
    context.user_data["payment"] = {
        "Patient_ID": patient.get("Patient_ID", ""),
        "Patient_Name": patient.get("Full_Name", ""),
        "Department": patient.get("Department", ""),
        "Sessions": 1,
    }
    await query.edit_message_text(
        _register_amount_prompt_text(patient.get("Full_Name", ""), patient.get("Patient_ID", ""), 1),
        reply_markup=_register_amount_keyboard(1),
    )
    return PAY_AMOUNT''',
)

apply(
    "5) নতুন register হেল্পার/হ্যান্ডলার ফাংশন যোগ",
    'async def reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):\n    staff = context.user_data.get("staff") or await _require_staff(update, context)',
    '''def _register_amount_keyboard(sessions: int) -> InlineKeyboardMarkup:
    sess_label = "🔁 ২ সেশন হয়েছে" if sessions == 1 else "🔁 ১ সেশনে ফেরত যাও"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(sess_label, callback_data="regsesstoggle")],
        [
            InlineKeyboardButton("৳400", callback_data="regamt_400"),
            InlineKeyboardButton("✏️ অন্য পরিমাণ", callback_data="regamt_custom"),
        ],
    ])


def _register_amount_prompt_text(patient_name: str, patient_id: str, sessions: int) -> str:
    return (
        f"রোগী: {patient_name} ({patient_id})\\n"
        f"সেশন: {sessions}  (ডিফল্ট ১, আজ ২টা সেশন হলে উপরের বাটনে চাপো)\\n\\n"
        "কত টাকা নেওয়া হলো?"
    )


def _register_view_text_and_keyboard():
    reg = sheets.get_daily_register()
    lines = [f"📋 আজকের রেজিস্টার ({reg['date']})", ""]
    if not reg["rows"]:
        lines.append("আজ এখনো কোনো এন্ট্রি হয়নি।")
    else:
        for r in reg["rows"]:
            lines.append(
                f"{r['Sl']}. {r['Patient_Name']} | সেশন {r['Sessions']} | "
                f"বিল {r['Bill']:.0f} | পেইড {r['Paid']:.0f} | বাকি {r['Due']:.0f} | {r['Status']}"
            )
        lines.append("")
        lines.append(f"👥 মোট রোগী: {reg['total_patients']} | 🩺 সেশন: {reg['total_sessions']}")
        lines.append(
            f"💵 বিল: {reg['total_bill']:.0f} | ✅ পেইড: {reg['total_paid']:.0f} | ⏳ বাকি: {reg['total_due']:.0f}"
        )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("➕ নতুন এন্ট্রি", callback_data="regnew")]])
    return "\\n".join(lines), keyboard


async def register_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return
    if not roles.can_access(staff.get("Role", ""), roles.MENU_DAILY_REGISTER):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return
    text, keyboard = _register_view_text_and_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard)


async def reg_new_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    context.user_data["payment"] = {}
    await query.message.reply_text("রোগীর নাম, ফোন নম্বর, অথবা Patient ID লিখো (খুঁজতে):")
    recent_kb = _recent_patient_buttons("paysel_")
    if recent_kb:
        await query.message.reply_text(
            "👥 অথবা সাম্প্রতিক রোগীদের মধ্য থেকে সরাসরি বেছে নাও:",
            reply_markup=recent_kb,
        )
    return PAY_SEARCH


async def reg_session_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    p = context.user_data.get("payment", {})
    sessions = 2 if p.get("Sessions", 1) == 1 else 1
    context.user_data.setdefault("payment", {})["Sessions"] = sessions
    await query.edit_message_text(
        _register_amount_prompt_text(p.get("Patient_Name", ""), p.get("Patient_ID", ""), sessions),
        reply_markup=_register_amount_keyboard(sessions),
    )
    return PAY_AMOUNT


async def reg_amount_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data.replace("regamt_", "")
    if choice == "custom":
        await query.edit_message_text("কত টাকা নেওয়া হলো লেখো (শুধু সংখ্যা):")
        return PAY_AMOUNT
    try:
        amount = float(choice)
    except ValueError:
        amount = 0.0
    context.user_data.setdefault("payment", {})["Amount"] = amount
    await query.edit_message_text(f"টাকা: {amount:.0f}")
    await query.message.reply_text(
        "Payment Method বেছে নাও:", reply_markup=_payment_method_keyboard()
    )
    return PAY_METHOD


async def reports_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)''',
)

apply(
    "6) pay_confirm-এ register view যোগ",
    '''        await update.message.reply_text(
            "\\n".join(lines), reply_markup=_menu_keyboard(staff.get("Role", ""))
        )
    except Exception as e:
        logger.exception("pay_confirm ব্যর্থ হয়েছে")''',
    '''        await update.message.reply_text(
            "\\n".join(lines), reply_markup=_menu_keyboard(staff.get("Role", ""))
        )
        reg_text, reg_kb = _register_view_text_and_keyboard()
        await update.message.reply_text(reg_text, reply_markup=reg_kb)
    except Exception as e:
        logger.exception("pay_confirm ব্যর্থ হয়েছে")''',
)

apply(
    "7) register_menu হ্যান্ডলার main()-এ যোগ",
    '''    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_TODAY_APPOINTMENTS}$"), today_appointments)
    )
    app.add_handler(CallbackQueryHandler(apt_status_callback, pattern="^aptstatus_"))''',
    '''    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_TODAY_APPOINTMENTS}$"), today_appointments)
    )
    app.add_handler(CallbackQueryHandler(apt_status_callback, pattern="^aptstatus_"))
    app.add_handler(
        MessageHandler(filters.Regex(f"^{roles.MENU_DAILY_REGISTER}$"), register_menu)
    )''',
)

apply(
    "8) pay_conv entry_points/states আপডেট",
    '''    pay_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_PAYMENT}$"), pay_start),
            CallbackQueryHandler(plist_action_pay, pattern="^plistact_pay_"),
        ],
        states={
            PAY_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_search)],
            PAY_SELECT: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_select),
            ],
            PAY_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_session)],
            PAY_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_amount)],
            PAY_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_method)],
            PAY_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_confirm)],
        },''',
    '''    pay_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_PAYMENT}$"), pay_start),
            CallbackQueryHandler(plist_action_pay, pattern="^plistact_pay_"),
            CallbackQueryHandler(reg_new_start, pattern="^regnew$"),
        ],
        states={
            PAY_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_search)],
            PAY_SELECT: [
                CallbackQueryHandler(pay_select_callback, pattern="^paysel_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_select),
            ],
            PAY_SESSION: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_session)],
            PAY_AMOUNT: [
                CallbackQueryHandler(reg_amount_callback, pattern="^regamt_"),
                CallbackQueryHandler(reg_session_toggle, pattern="^regsesstoggle$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_amount),
            ],
            PAY_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_method)],
            PAY_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), pay_confirm)],
        },''',
)

with open(PATH, "w", encoding="utf-8") as f:
    f.write(src)

print("\n---- ফলাফল ----")
all_ok = True
for label, ok, count in changes:
    mark = "✅" if ok else "❌"
    print(f"{mark} {label} (matches found: {count})")
    if not ok:
        all_ok = False

if all_ok:
    print("\n🎉 সব পরিবর্তন সফলভাবে হয়েছে। এখন py_compile দিয়ে চেক করো:")
    print("   python3 -m py_compile bot.py")
else:
    print(f"\n⚠️ কিছু পরিবর্তন ব্যর্থ হয়েছে। {BACKUP} থেকে রিস্টোর করে আমাকে জানাও।")
