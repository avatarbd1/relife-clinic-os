# -*- coding: utf-8 -*-
import sys

path = "bot.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

if "cs_session_id" in src:
    sys.exit("bot.py already patched (cs_session_id exists) — nothing to do.")

if "import time" not in src.split("\n\n")[0] and "\nimport time\n" not in src:
    # নিশ্চিত করা যে time মডিউল ইমপোর্ট করা আছে
    src = src.replace("import os\n", "import os\nimport time\n", 1)

old_select = '''    context.user_data["cs_case_context"] = case_context
    await query.edit_message_text(
        "\\u2705 রোগীর ডেটা লোড হয়েছে।\\n"
        "কেসের বাড়তি কোনো তথ্য/অবজারভেশন থাকলে লেখো, না থাকলে শুধু 'না' লিখো।"
    )
    return CASESTUDY_EXTRA'''
new_select = '''    context.user_data["cs_case_context"] = case_context
    context.user_data["cs_patient_id"] = patient_id
    patient = sheets.get_patient_by_id(patient_id) or {}
    context.user_data["cs_patient_name"] = patient.get("Full_Name") or patient.get("Name") or ""
    context.user_data["cs_session_id"] = f"CS-{patient_id}-{int(time.time())}"
    await query.edit_message_text(
        "\\u2705 রোগীর ডেটা লোড হয়েছে।\\n"
        "কেসের বাড়তি কোনো তথ্য/অবজারভেশন থাকলে লেখো, না থাকলে শুধু 'না' লিখো।"
    )
    return CASESTUDY_EXTRA'''
if src.count(old_select) != 1:
    sys.exit("ABORT: casestudy_select_callback block not found exactly once.")
src = src.replace(old_select, new_select, 1)

old_extra = '''    context.user_data["cs_case_text"] = case_text
    context.user_data["cs_lesson"] = 1
    await update.message.reply_text("\\U0001F914 কেস বিশ্লেষণ করছি, Lesson 1 তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, 1)
    await update.message.reply_text(answer, reply_markup=_cslesson_next_keyboard())
    return CASESTUDY_LESSON'''
new_extra = '''    context.user_data["cs_case_text"] = case_text
    context.user_data["cs_lesson"] = 1
    await update.message.reply_text("\\U0001F914 কেস বিশ্লেষণ করছি, Lesson 1 তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, 1)
    staff = context.user_data.get("staff", {})
    try:
        sheets.add_case_study_lesson(
            context.user_data.get("cs_session_id", ""),
            context.user_data.get("cs_patient_id", ""),
            context.user_data.get("cs_patient_name", ""),
            1,
            case_study_ai.LESSON_TITLES[0],
            answer,
            staff.get("Full_Name") or staff.get("Name") or str(staff.get("Staff_ID", "")),
        )
    except Exception:
        pass
    await update.message.reply_text(answer, reply_markup=_cslesson_next_keyboard())
    return CASESTUDY_LESSON'''
if src.count(old_extra) != 1:
    sys.exit("ABORT: casestudy_extra_receive block not found exactly once.")
src = src.replace(old_extra, new_extra, 1)

old_lesson_cb = '''    lesson += 1
    await query.message.reply_text(f"\\U0001F914 Lesson {lesson} তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, lesson)
    context.user_data["cs_lesson"] = lesson

    if lesson >= len(case_study_ai.LESSON_TITLES):'''
new_lesson_cb = '''    lesson += 1
    await query.message.reply_text(f"\\U0001F914 Lesson {lesson} তৈরি হচ্ছে...")
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

    if lesson >= len(case_study_ai.LESSON_TITLES):'''
if src.count(old_lesson_cb) != 1:
    sys.exit("ABORT: casestudy_lesson_callback block not found exactly once.")
src = src.replace(old_lesson_cb, new_lesson_cb, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("bot.py: patched OK")
