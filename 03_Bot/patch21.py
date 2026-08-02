# -*- coding: utf-8 -*-
import sys

path_ai = "case_study_ai.py"
path_bot = "bot.py"

with open(path_ai, "r", encoding="utf-8") as f:
    ai_src = f.read()
with open(path_bot, "r", encoding="utf-8") as f:
    bot_src = f.read()

if "import requests" not in ai_src:
    sys.exit("ABORT: 'import requests' not found in case_study_ai.py.")
need_json_import = "import json" not in ai_src

if "def check_lesson_questions" in ai_src:
    sys.exit("ABORT: check_lesson_questions() already exists — patch already applied?")

new_func = '''

def check_lesson_questions(case_text: str, lesson_number: int) -> list:
    """এই Lesson international case-competition মানে লিখতে আরও patient-detail দরকার কিনা AI নিজে যাচাই করে।
    দরকার হলে সর্বোচ্চ ১০টা নির্দিষ্ট প্রশ্ন (list of str) রিটার্ন করে, দরকার না হলে খালি list।"""
    if not OPENROUTER_API_KEY:
        return []

    title = LESSON_TITLES[lesson_number - 1]
    system_msg = (
        "তুমি একজন Senior Physiotherapy Clinical Mentor। ব্যবহারকারী একটা রোগীর কেস দিয়েছে এবং "
        f"এখন এই Lesson লিখতে চাও: \\"{title}\\"। "
        "এই Lesson international physiotherapy case-competition মানের (sharp, patient-specific reasoning সহ) "
        "লিখতে দেওয়া তথ্য যথেষ্ট কিনা যাচাই করো। "
        "যথেষ্ট না হলে সর্বোচ্চ ১০টা নির্দিষ্ট, সংক্ষিপ্ত প্রশ্ন লেখো যা মিসিং তথ্য জানতে সাহায্য করবে — "
        "শুধু সেই প্রশ্নগুলোই লেখো যেগুলোর উত্তর সত্যিই এই Lesson-এর মান বাড়াবে, অপ্রয়োজনীয় প্রশ্ন কোরো না। "
        "উত্তর অবশ্যই শুধুমাত্র একটা JSON array of strings হতে হবে — অন্য কোনো টেক্সট, ব্যাখ্যা বা মার্কডাউন ছাড়া। "
        "তথ্য যথেষ্ট মনে হলে খালি array [] রিটার্ন করো।"
    )
    user_msg = f"রোগীর কেস: {case_text}"

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 500,
            },
            timeout=40,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        content = content.replace("```json", "").replace("```", "").strip()
        questions = json.loads(content)
        if isinstance(questions, list):
            return [str(q).strip() for q in questions if str(q).strip()][:10]
        return []
    except Exception as e:
        print(f"[case_study_ai] check_lesson_questions FAILED: {e}")
        return []
'''

bot_replacements = []

old_b1 = "(CASESTUDY_SEARCH, CASESTUDY_EXTRA) = range(40, 42)"
new_b1 = "(CASESTUDY_SEARCH, CASESTUDY_EXTRA) = range(40, 42)\n(CASESTUDY_QUESTION,) = range(42, 43)"
bot_replacements.append((old_b1, new_b1))

old_b2 = '    context.user_data["cs_case_text"] = case_text\n    context.user_data["cs_lesson"] = 1'
new_b2 = '''    context.user_data["cs_case_text"] = case_text

    questions = case_study_ai.check_lesson_questions(case_text, 1)
    if questions:
        context.user_data["cs_pending_lesson"] = 1
        numbered = "\\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        await update.message.reply_text(
            "এই Lesson আরো ভালোভাবে লিখতে কিছু তথ্য দরকার:\\n\\n"
            f"{numbered}\\n\\n"
            "যতটুকু জানো লিখে পাঠাও (না জানলে 'জানি না' লিখো):"
        )
        return CASESTUDY_QUESTION

    context.user_data["cs_lesson"] = 1'''
bot_replacements.append((old_b2, new_b2))

old_b3 = '''    lesson += 1
    await query.message.reply_text(f"\\U0001F914 Lesson {lesson} \u09a4\u09c8\u09b0\u09bf \u09b9\u099a\u09cd\u099b\u09c7...")
    answer = case_study_ai.answer_case_lesson(case_text, lesson)'''
new_b3 = '''    lesson += 1

    questions = case_study_ai.check_lesson_questions(case_text, lesson)
    if questions:
        context.user_data["cs_pending_lesson"] = lesson
        numbered = "\\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        await query.message.reply_text(
            "এই Lesson আরো ভালোভাবে লিখতে কিছু তথ্য দরকার:\\n\\n"
            f"{numbered}\\n\\n"
            "যতটুকু জানো লিখে পাঠাও (না জানলে 'জানি না' লিখো):"
        )
        return CASESTUDY_QUESTION

    await query.message.reply_text(f"\\U0001F914 Lesson {lesson} \u09a4\u09c8\u09b0\u09bf \u09b9\u099a\u09cd\u099b\u09c7...")
    answer = case_study_ai.answer_case_lesson(case_text, lesson)'''
bot_replacements.append((old_b3, new_b3))

old_b4 = "async def casestudy_cancel(update, context):"
new_b4 = '''async def casestudy_question_receive(update, context):
    text = update.message.text.strip()
    lesson = context.user_data.get("cs_pending_lesson", context.user_data.get("cs_lesson", 1) + 1)
    case_text = context.user_data.get("cs_case_text", "")
    if text not in ("\u099c\u09be\u09a8\u09bf \u09a8\u09be", "na", "n/a", "N/A", "No", "no"):
        case_text += f"\\n\\nLesson {lesson}-\u098f\u09b0 \u099c\u09a8\u09cd\u09af \u09ac\u09be\u09dc\u09a4\u09bf \u09a4\u09a5\u09cd\u09af:\\n{text}"
        context.user_data["cs_case_text"] = case_text
    staff = context.user_data.get("staff", {})
    await update.message.reply_text(f"\\U0001F914 Lesson {lesson} \u09a4\u09c8\u09b0\u09bf \u09b9\u099a\u09cd\u099b\u09c7...")
    answer = case_study_ai.answer_case_lesson(case_text, lesson)
    context.user_data["cs_lesson"] = lesson
    try:
        sheets.add_case_study_lesson(
            context.user_data.get("cs_session_id", ""),
            context.user_data.get("cs_patient_id", ""),
            context.user_data.get("cs_patient_name", ""),
            lesson,
            case_study_ai.LESSON_TITLES[lesson - 1],
            answer,
            staff.get("Full_Name") or staff.get("Name") or str(staff.get("Staff_ID", "")),
        )
    except Exception:
        pass

    if lesson >= len(case_study_ai.LESSON_TITLES):
        await update.message.reply_text(
            answer,
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
        return ConversationHandler.END

    await update.message.reply_text(answer, reply_markup=_cslesson_next_keyboard())
    return CASESTUDY_LESSON


async def casestudy_cancel(update, context):'''
bot_replacements.append((old_b4, new_b4))

old_b5 = '''            CASESTUDY_EXTRA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_extra_receive)
            ],
            CASESTUDY_LESSON: ['''
new_b5 = '''            CASESTUDY_EXTRA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_extra_receive)
            ],
            CASESTUDY_QUESTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_question_receive)
            ],
            CASESTUDY_LESSON: ['''
bot_replacements.append((old_b5, new_b5))

for i, (old, new) in enumerate(bot_replacements, 1):
    count = bot_src.count(old)
    if count != 1:
        sys.exit(f"ABORT: bot.py replacement #{i} matched {count} times (expected 1). Nothing written.")

if need_json_import:
    ai_src = ai_src.replace("import requests", "import requests\nimport json", 1)
ai_src = ai_src.rstrip("\n") + "\n" + new_func + "\n"

for old, new in bot_replacements:
    bot_src = bot_src.replace(old, new, 1)

with open(path_ai, "w", encoding="utf-8") as f:
    f.write(ai_src)
with open(path_bot, "w", encoding="utf-8") as f:
    f.write(bot_src)

print("PATCH21 APPLIED OK — case_study_ai.py + bot.py both updated (pre-lesson AI question flow)")
