"""
Relife Clinic - Telegram Management Bot (Role-based)
Owner / Receptionist / Therapist / Manager - shobar jonno alada menu.
"""
import logging

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
import sheets
import roles

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

(
    ADD_PATIENT_NAME, ADD_PATIENT_PHONE,
    ADD_APPT_PATIENT, ADD_APPT_DATE, ADD_APPT_TIME, ADD_APPT_DOCTOR,
    ADD_PAYMENT_PATIENT, ADD_PAYMENT_AMOUNT, ADD_PAYMENT_METHOD,
    ADD_NOTE_PATIENT, ADD_NOTE_TEXT,
) = range(11)


async def guard(update: Update):
    user_id = update.effective_user.id
    info = roles.get_staff_info(user_id)
    if not info:
        await update.effective_message.reply_text(
            f"Tumi ei bot use korar onumoti pao ni.\n"
            f"Tomar Telegram ID: {user_id}\n"
            "Ei ID ta roles.py file-e jog korte bolo malik-ke."
        )
        return None
    return info


def menu_for_role(role: str):
    buttons = []
    if role == "owner":
        buttons = [
            [InlineKeyboardButton("Ajker Appointment", callback_data="today_appt")],
            [InlineKeyboardButton("Notun Rogi", callback_data="add_patient")],
            [InlineKeyboardButton("Notun Appointment", callback_data="add_appt")],
            [InlineKeyboardButton("Ajker Payment", callback_data="today_payment")],
            [InlineKeyboardButton("Payment Jog Koro", callback_data="add_payment")],
            [InlineKeyboardButton("Staff Talika", callback_data="staff_list")],
            [InlineKeyboardButton("Inventory", callback_data="inventory")],
            [InlineKeyboardButton("Reports", callback_data="reports")],
        ]
    elif role == "receptionist":
        buttons = [
            [InlineKeyboardButton("Ajker Appointment", callback_data="today_appt")],
            [InlineKeyboardButton("Notun Rogi", callback_data="add_patient")],
            [InlineKeyboardButton("Notun Appointment", callback_data="add_appt")],
            [InlineKeyboardButton("Ajker Payment", callback_data="today_payment")],
            [InlineKeyboardButton("Payment Jog Koro", callback_data="add_payment")],
        ]
    elif role == "therapist":
        buttons = [
            [InlineKeyboardButton("Ajker Amar Session", callback_data="my_sessions")],
            [InlineKeyboardButton("Treatment Note Jog Koro", callback_data="add_note")],
        ]
    elif role == "manager":
        buttons = [
            [InlineKeyboardButton("Appointment Overview", callback_data="today_appt")],
            [InlineKeyboardButton("Inventory", callback_data="inventory")],
            [InlineKeyboardButton("Reports", callback_data="reports")],
        ]
    return InlineKeyboardMarkup(buttons)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    info = await guard(update)
    if not info:
        return
    await update.message.reply_text(
        f"Shagotom, {info['name']} ({info['role'].title()})!\n\nEkta option bechhe nao:",
        reply_markup=menu_for_role(info["role"]),
    )


async def show_main_menu(query, info):
    await query.edit_message_text(
        f"Main Menu ({info['role'].title()})\n\nEkta option bechhe nao:",
        reply_markup=menu_for_role(info["role"]),
    )


def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("Ferot", callback_data="main_menu")]])


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    info = roles.get_staff_info(query.from_user.id)
    if not info:
        await query.answer("Tumi ei bot use korte paro na.", show_alert=True)
        return
    await query.answer()
    data = query.data
    role = info["role"]

    if data == "main_menu":
        await show_main_menu(query, info)
        return

    if data == "today_appt" and roles.has_permission(query.from_user.id, "appointments"):
        appts = sheets.get_today_appointments()
        if not appts:
            text = "Ajke kono appointment nei."
        else:
            lines = ["Ajker Appointment:\n"]
            for a in appts:
                lines.append(f"- {a.get('Time')} - {a.get('Patient')} (Dr. {a.get('Doctor')}) [{a.get('Status')}]")
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=back_button())

    elif data == "today_payment" and roles.has_permission(query.from_user.id, "payments"):
        total, entries = sheets.get_today_payments()
        text = f"Ajker Mot Payment: {total:.2f} Taka\n\n"
        for e in entries[-10:]:
            text += f"- {e.get('Patient')} - {e.get('Amount')} Tk ({e.get('Method')})\n"
        await query.edit_message_text(text or "Kono entry nei.", reply_markup=back_button())

    elif data == "staff_list" and roles.has_permission(query.from_user.id, "staff"):
        staff_rows = [f"- {v['name']} - {v['role'].title()}" for v in roles.STAFF.values()]
        text = "Staff Talika:\n\n" + "\n".join(staff_rows)
        await query.edit_message_text(text, reply_markup=back_button())

    elif data == "inventory" and roles.has_permission(query.from_user.id, "inventory"):
        items = sheets.get_inventory()
        if not items:
            text = "Inventory-te kichu nei."
        else:
            lines = ["Inventory:\n"]
            for i in items:
                lines.append(f"- {i.get('Item')}: {i.get('Quantity')} {i.get('Unit')}")
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=back_button())

    elif data == "reports" and roles.has_permission(query.from_user.id, "reports"):
        total_pay, _ = sheets.get_today_payments()
        appts = sheets.get_today_appointments()
        text = (
            "Ajker Report:\n\n"
            f"- Mot Appointment: {len(appts)}\n"
            f"- Mot Payment: {total_pay:.2f} Taka\n"
        )
        await query.edit_message_text(text, reply_markup=back_button())

    elif data == "my_sessions" and role == "therapist":
        sessions = sheets.get_sessions_for_therapist_today(info["name"])
        if not sessions:
            text = "Ajke tomar kono session nei."
        else:
            lines = ["Ajker Session:\n"]
            for s in sessions:
                lines.append(f"- {s.get('Time')} - {s.get('Patient')} [{s.get('Status')}]")
            text = "\n".join(lines)
        await query.edit_message_text(text, reply_markup=back_button())

    else:
        await query.answer("Ei option-er onumoti nei.", show_alert=True)


async def add_patient_start(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Rogi-r naam likho:")
    return ADD_PATIENT_NAME

async def add_patient_name(update, context):
    context.user_data["patient_name"] = update.message.text
    await update.message.reply_text("Rogi-r phone number likho:")
    return ADD_PATIENT_PHONE

async def add_patient_phone(update, context):
    phone = update.message.text
    name = context.user_data.get("patient_name")
    sheets.add_patient(name, phone)
    info = roles.get_staff_info(update.effective_user.id)
    await update.message.reply_text(f"Rogi joma hoyeche: {name} ({phone})", reply_markup=menu_for_role(info["role"]))
    return ConversationHandler.END


async def add_appt_start(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Rogi-r naam likho:")
    return ADD_APPT_PATIENT

async def add_appt_patient(update, context):
    context.user_data["appt_patient"] = update.message.text
    await update.message.reply_text("Tarikh likho (jemon: 2026-07-15):")
    return ADD_APPT_DATE

async def add_appt_date(update, context):
    context.user_data["appt_date"] = update.message.text
    await update.message.reply_text("Shomoy likho (jemon: 05:30 PM):")
    return ADD_APPT_TIME

async def add_appt_time(update, context):
    context.user_data["appt_time"] = update.message.text
    await update.message.reply_text("Therapist/Doctor-er naam likho:")
    return ADD_APPT_DOCTOR

async def add_appt_doctor(update, context):
    doctor = update.message.text
    sheets.add_appointment(
        context.user_data.get("appt_patient"),
        context.user_data.get("appt_date"),
        context.user_data.get("appt_time"),
        doctor,
    )
    info = roles.get_staff_info(update.effective_user.id)
    await update.message.reply_text("Appointment joma hoyeche!", reply_markup=menu_for_role(info["role"]))
    return ConversationHandler.END


async def add_payment_start(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Kon rogir payment? Naam likho:")
    return ADD_PAYMENT_PATIENT

async def add_payment_patient(update, context):
    context.user_data["pay_patient"] = update.message.text
    await update.message.reply_text("Koto taka? (shudhu number likho):")
    return ADD_PAYMENT_AMOUNT

async def add_payment_amount(update, context):
    text = update.message.text.strip()
    try:
        amount = float(text)
    except ValueError:
        await update.message.reply_text("Shudhu number likho. Abar chesta koro:")
        return ADD_PAYMENT_AMOUNT
    context.user_data["pay_amount"] = amount
    await update.message.reply_text("Kon method-e payment? (Cash / bKash / Card):")
    return ADD_PAYMENT_METHOD

async def add_payment_method(update, context):
    method = update.message.text
    sheets.add_payment(
        context.user_data.get("pay_patient"),
        context.user_data.get("pay_amount"),
        method,
    )
    info = roles.get_staff_info(update.effective_user.id)
    await update.message.reply_text("Payment joma hoyeche!", reply_markup=menu_for_role(info["role"]))
    return ConversationHandler.END


async def add_note_start(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Kon rogir jonno note? Naam likho:")
    return ADD_NOTE_PATIENT

async def add_note_patient(update, context):
    context.user_data["note_patient"] = update.message.text
    await update.message.reply_text("Treatment note likho:")
    return ADD_NOTE_TEXT

async def add_note_text(update, context):
    note = update.message.text
    info = roles.get_staff_info(update.effective_user.id)
    sheets.add_therapy_note(info["name"], context.user_data.get("note_patient"), note)
    await update.message.reply_text("Note joma hoyeche!", reply_markup=menu_for_role(info["role"]))
    return ConversationHandler.END


async def cancel(update, context):
    info = roles.get_staff_info(update.effective_user.id)
    await update.message.reply_text("Baatil kora holo.", reply_markup=menu_for_role(info["role"]) if info else None)
    return ConversationHandler.END


def main():
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN pawa jai ni. .env file check koro.")

    app = Application.builder().token(config.BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_patient_start, pattern="^add_patient$")],
        states={
            ADD_PATIENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_patient_name)],
            ADD_PATIENT_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_patient_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_appt_start, pattern="^add_appt$")],
        states={
            ADD_APPT_PATIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_appt_patient)],
            ADD_APPT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_appt_date)],
            ADD_APPT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_appt_time)],
            ADD_APPT_DOCTOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_appt_doctor)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_payment_start, pattern="^add_payment$")],
        states={
            ADD_PAYMENT_PATIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payment_patient)],
            ADD_PAYMENT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payment_amount)],
            ADD_PAYMENT_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payment_method)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(add_note_start, pattern="^add_note$")],
        states={
            ADD_NOTE_PATIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_patient)],
            ADD_NOTE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    ))

    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot chalu hocche...")
    app.run_polling()


if __name__ == "__main__":
    main()
