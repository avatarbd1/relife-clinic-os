# -*- coding: utf-8 -*-
import sys

# ---------- case_study_ai.py: "দাও" টাইপ করার ইন্সট্রাকশন লাইন সরানো ----------
path1 = "case_study_ai.py"
with open(path1, "r", encoding="utf-8") as f:
    src1 = f.read()

old_next_line = '''    if lesson_number < len(LESSON_TITLES):
        user_msg += "\\n\\nএই Lesson-এর একদম শেষে হুবহু এই লাইনটা লিখো: \\"পরবর্তী Lesson দেখতে শুধু 'দাও' লিখুন।\\""
    else:'''
new_next_line = '''    if lesson_number < len(LESSON_TITLES):
        pass
    else:'''
if old_next_line in src1:
    src1 = src1.replace(old_next_line, new_next_line, 1)
    with open(path1, "w", encoding="utf-8") as f:
        f.write(src1)
    print("case_study_ai.py: patched OK")
else:
    print("case_study_ai.py: pattern not found — already patched? skip")

# ---------- bot.py: বাটন যোগ করা ----------
path2 = "bot.py"
with open(path2, "r", encoding="utf-8") as f:
    src2 = f.read()

if "cslesson_next" in src2:
    sys.exit("bot.py already patched (cslesson_next exists) — nothing to do.")

# 1) keyboard helper যোগ করা casestudy_start এর ঠিক আগে
anchor = "async def casestudy_start(update, context):"
if src2.count(anchor) != 1:
    sys.exit("ABORT: casestudy_start anchor not found once.")
helper = '''def _cslesson_next_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("➡️ পরবর্তী Lesson", callback_data="cslesson_next")]]
    )


'''
src2 = src2.replace(anchor, helper + anchor, 1)

# 2) casestudy_receive + casestudy_lesson_receive পুরোটা replace
start_fn = "async def casestudy_receive(update, context):"
end_fn = "async def casestudy_cancel(update, context):"
si = src2.find(start_fn)
ei = src2.find(end_fn)
if si == -1 or ei == -1 or ei <= si:
    sys.exit("ABORT: casestudy_receive/casestudy_cancel boundary not found.")

new_fns = '''async def casestudy_receive(update, context):
    staff = context.user_data.get("staff", {})
    case_text = update.message.text.strip()
    context.user_data["cs_case_text"] = case_text
    context.user_data["cs_lesson"] = 1
    await update.message.reply_text("\\U0001F914 কেস বিশ্লেষণ করছি, Lesson 1 তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, 1)
    await update.message.reply_text(answer, reply_markup=_cslesson_next_keyboard())
    return CASESTUDY_LESSON


async def casestudy_lesson_callback(update, context):
    query = update.callback_query
    await query.answer()
    staff = context.user_data.get("staff", {})
    case_text = context.user_data.get("cs_case_text", "")
    lesson = context.user_data.get("cs_lesson", 1)

    lesson += 1
    await query.message.reply_text(f"\\U0001F914 Lesson {lesson} তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, lesson)
    context.user_data["cs_lesson"] = lesson

    if lesson >= len(case_study_ai.LESSON_TITLES):
        await query.message.reply_text(
            answer,
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
        return ConversationHandler.END

    await query.message.reply_text(answer, reply_markup=_cslesson_next_keyboard())
    return CASESTUDY_LESSON


'''
src2 = src2[:si] + new_fns + src2[ei:]

# 3) ConversationHandler states আপডেট — CASESTUDY_LESSON এ text handler এর বদলে callback handler
old_state_block = '''            CASESTUDY_LESSON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_lesson_receive)
            ],'''
new_state_block = '''            CASESTUDY_LESSON: [
                CallbackQueryHandler(casestudy_lesson_callback, pattern="^cslesson_next$")
            ],'''
if src2.count(old_state_block) != 1:
    sys.exit("ABORT: CASESTUDY_LESSON state block not found exactly once.")
src2 = src2.replace(old_state_block, new_state_block, 1)

with open(path2, "w", encoding="utf-8") as f:
    f.write(src2)
print("bot.py: patched OK")
print("DONE")
