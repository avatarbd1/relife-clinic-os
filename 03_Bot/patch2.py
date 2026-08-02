# -*- coding: utf-8 -*-
import sys

path2 = "bot.py"
with open(path2, "r", encoding="utf-8") as f:
    src2 = f.read()

if "CASESTUDY_LESSON" in src2:
    sys.exit("bot.py already patched (CASESTUDY_LESSON exists) — nothing to do.")

old_state = "(CASESTUDY_INPUT,) = range(38, 39)"
if src2.count(old_state) != 1:
    sys.exit("ABORT: state line not found exactly once. Run: grep -n CASESTUDY_INPUT bot.py")
src2 = src2.replace(old_state, old_state + "\n(CASESTUDY_LESSON,) = range(39, 40)", 1)

start_fn = "async def casestudy_receive(update, context):"
end_fn = "async def casestudy_cancel(update, context):"
si = src2.find(start_fn)
ei = src2.find(end_fn)
if si == -1 or ei == -1 or ei <= si:
    sys.exit("ABORT: casestudy_receive/casestudy_cancel boundary not found. Run: grep -n 'async def casestudy' bot.py")

new_fns = '''async def casestudy_receive(update, context):
    staff = context.user_data.get("staff", {})
    case_text = update.message.text.strip()
    context.user_data["cs_case_text"] = case_text
    context.user_data["cs_lesson"] = 1
    await update.message.reply_text("\\U0001F914 কেস বিশ্লেষণ করছি, Lesson 1 তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, 1)
    await update.message.reply_text(answer)
    return CASESTUDY_LESSON


async def casestudy_lesson_receive(update, context):
    staff = context.user_data.get("staff", {})
    text = update.message.text.strip()
    case_text = context.user_data.get("cs_case_text", "")
    lesson = context.user_data.get("cs_lesson", 1)

    if text != "দাও":
        await update.message.reply_text(
            "পরবর্তী Lesson দেখতে শুধু 'দাও' লিখুন, অথবা /cancel দিয়ে বাতিল করুন।"
        )
        return CASESTUDY_LESSON

    lesson += 1
    await update.message.reply_text(f"\\U0001F914 Lesson {lesson} তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, lesson)
    context.user_data["cs_lesson"] = lesson

    if lesson >= len(case_study_ai.LESSON_TITLES):
        await update.message.reply_text(
            answer,
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
        return ConversationHandler.END

    await update.message.reply_text(answer)
    return CASESTUDY_LESSON


'''
src2 = src2[:si] + new_fns + src2[ei:]

start_conv = "casestudy_conv = ConversationHandler("
end_conv = "app.add_handler(casestudy_conv)"
si2 = src2.find(start_conv)
ei2 = src2.find(end_conv)
if si2 == -1 or ei2 == -1 or ei2 <= si2:
    sys.exit("ABORT: casestudy_conv registration boundary not found. Run: grep -n 'casestudy_conv' bot.py")
ei2_end = ei2 + len(end_conv)

new_conv = '''casestudy_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_CASE_STUDY}$"), casestudy_start)
        ],
        states={
            CASESTUDY_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_receive)
            ],
            CASESTUDY_LESSON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_lesson_receive)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", casestudy_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(casestudy_conv)'''
src2 = src2[:si2] + new_conv + src2[ei2_end:]

with open(path2, "w", encoding="utf-8") as f:
    f.write(src2)
print("bot.py: patched OK")
print("DONE")
