async def salary_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_SALARY):
        await update.message.reply_text("⛔ এই মেনুতে তোমার অনুমতি নেই।")
        return ConversationHandler.END
    all_staff = [s for s in sheets.get_all_staff() if s.get("Staff_ID")]
    if not all_staff:
        await update.message.reply_text("❌ কোনো স্টাফ পাওয়া যায়নি।")
        return ConversationHandler.END
    buttons = []
    for s in all_staff:
        name = s.get("Full_Name", "")
        role = s.get("Role", "")
        sid = s.get("Staff_ID")
        label = f"{name} ({role})"
        buttons.append([InlineKeyboardButton(label, callback_data=f"salsel_{sid}")])
    await update.message.reply_text("কোন স্টাফের বেতন দেবে?", reply_markup=InlineKeyboardMarkup(buttons))
    return SALARY_SELECT_STAFF


async def salary_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    staff_id = query.data.replace("salsel_", "", 1)
    month = bd_now().strftime("%Y-%m")
    summary = sheets.get_salary_summary(staff_id, month)
    if not summary:
        await query.edit_message_text("❌ স্টাফ পাওয়া যায়নি।")
        return ConversationHandler.END

    name = summary["Full_Name"]
    monthly_salary = summary["Monthly_Salary"]
    paid = summary["Paid"]
    due = summary["Due"]

    if monthly_salary <= 0:
        await query.edit_message_text(
            f"⚠️ {name}-এর জন্য 08_Staff শীটে Salary সেট করা নেই। আগে সেটা ঠিক করো।"
        )
        return ConversationHandler.END
    if due <= 0:
        await query.edit_message_text(
            f"✅ {name}-এর এই মাসের ({month}) বেতন সম্পূর্ণ পরিশোধ হয়েছে।\n"
            f"বেতন: ৳{monthly_salary:.0f} | পরিশোধিত: ৳{paid:.0f}"
        )
        return ConversationHandler.END

    context.user_data["salary"] = {
        "Staff_ID": staff_id,
        "Full_Name": name,
        "Telegram_ID": summary["Telegram_ID"],
        "Month": month,
        "Monthly_Salary": monthly_salary,
        "Paid": paid,
        "Due": due,
    }
    await query.edit_message_text(
        f"👤 {name} — {month}\n"
        f"মোট বেতন: ৳{monthly_salary:.0f}\n"
        f"পরিশোধিত: ৳{paid:.0f}\n"
        f"বাকি: ৳{due:.0f}\n\n"
        "কত টাকা দিচ্ছো লেখো:"
    )
    return SALARY_ENTER_AMOUNT


async def salary_amount_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    s = context.user_data.get("salary", {})
    due = s.get("Due", 0)
    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("❌ শুধু সংখ্যা লেখো (যেমন: 5000):")
        return SALARY_ENTER_AMOUNT
    if amount <= 0:
        await update.message.reply_text("❌ Amount অবশ্যই ০-এর বেশি হতে হবে:")
        return SALARY_ENTER_AMOUNT
    if amount > due:
        await update.message.reply_text(
            f"❌ বাকি আছে ৳{due:.0f}, কিন্তু তুমি ৳{amount:.0f} দিতে চাইছো। "
            "আবার লেখো (বাকির বেশি দেওয়া যাবে না):"
        )
        return SALARY_ENTER_AMOUNT
    s["Amount"] = amount
    context.user_data["salary"] = s
    await update.message.reply_text("কোনো নোট থাকলে লেখো, না থাকলে '-' দাও:")
    return SALARY_NOTE


async def salary_note_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    s = context.user_data.get("salary", {})
    s["Note"] = "" if text == "-" else text
    context.user_data["salary"] = s
    name = s.get("Full_Name", "")
    month = s.get("Month", "")
    amount = s.get("Amount", 0)
    note = s.get("Note") or "-"
    summary = (
        f"👤 {name} — {month}\n"
        f"পরিশোধ: ৳{amount:.0f}\n"
        f"নোট: {note}\n\n"
        "নিশ্চিত করো:"
    )
    confirm_keyboard = ReplyKeyboardMarkup([["হ্যাঁ", "না"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(summary, reply_markup=confirm_keyboard)
    return SALARY_CONFIRM


async def salary_confirm_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().lower()
    staff = context.user_data.get("staff", {})
    s = context.user_data.get("salary", {})

    if text not in ("হ্যাঁ", "yes", "y", "হা", "ha"):
        context.user_data.pop("salary", None)
        await update.message.reply_text("❌ বাতিল করা হয়েছে।", reply_markup=_menu_keyboard(staff.get("Role", "")))
        return ConversationHandler.END

    paid_by_name = staff.get("Full_Name") or staff.get("Name") or str(staff.get("Staff_ID", ""))
    staff_full_name = s.get("Full_Name", "")
    amount = s.get("Amount", 0)
    due = s.get("Due", 0)
    remaining_due = due - amount

    try:
        payment_id = sheets.add_salary_payment(
            s["Staff_ID"], s["Month"], amount,
            paid_by=paid_by_name,
            note=s.get("Note", ""),
        )
        await update.message.reply_text(
            f"✅ বেতন কিস্তি সেভ হয়েছে! Payment ID: {payment_id}\n"
            f"এই মাসের বাকি: ৳{remaining_due:.0f}",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )

        staff_telegram_id = s.get("Telegram_ID")
        if staff_telegram_id:
            try:
                await context.bot.send_message(
                    chat_id=int(staff_telegram_id),
                    text=(
                        "💰 আপনার বেতনের কিস্তি প্রদান করা হয়েছে।\n"
                        f"এই কিস্তি: ৳{amount:.0f}\n"
                        f"এই মাসের বাকি: ৳{remaining_due:.0f}\n"
                        "ধন্যবাদ।"
                    ),
                )
            except Exception:
                logger.exception(f"salary_confirm_receive: স্টাফ {staff_telegram_id}-কে notify করতে ব্যর্থ")

        try:
            for o in sheets.get_all_staff():
                if str(o.get("Role", "")).strip() != "Owner":
                    continue
                if str(o.get("Staff_ID", "")) == str(staff.get("Staff_ID", "")):
                    continue
                owner_telegram_id = o.get("Telegram_ID")
                if not owner_telegram_id:
                    continue
                try:
                    await context.bot.send_message(
                        chat_id=int(owner_telegram_id),
                        text=(
                            f"💰 {staff_full_name}-কে বেতনের কিস্তি দেওয়া হয়েছে ({paid_by_name})।\n"
                            f"কিস্তি: ৳{amount:.0f}\n"
                            f"এই মাসের বাকি: ৳{remaining_due:.0f}"
                        ),
                    )
                except Exception:
                    logger.exception(f"salary_confirm_receive: Owner {owner_telegram_id}-কে notify করতে ব্যর্থ")
        except Exception:
            logger.exception("salary_confirm_receive: Owner লিস্ট আনতে ব্যর্থ")

    except Exception as e:
        logger.exception("salary_confirm_receive ব্যর্থ হয়েছে")
        await update.message.reply_text(
            f"❌ সেভ করতে সমস্যা হয়েছে।\nError: {e}",
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
    context.user_data.pop("salary", None)
    return ConversationHandler.END


async def salary_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    staff = context.user_data.get("staff", {})
    context.user_data.pop("salary", None)
    await update.message.reply_text("❌ বাতিল করা হলো।", reply_markup=_menu_keyboard(staff.get("Role", "")))
    return ConversationHandler.END


