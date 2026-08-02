# -*- coding: utf-8 -*-
import sys

path2 = "bot.py"
with open(path2, "r", encoding="utf-8") as f:
    src2 = f.read()

if "CASESTUDY_SEARCH" in src2:
    sys.exit("bot.py already patched (CASESTUDY_SEARCH exists) — nothing to do.")

# 1) নতুন state constants
old_state = "(CASESTUDY_LESSON,) = range(39, 40)"
if src2.count(old_state) != 1:
    sys.exit("ABORT: CASESTUDY_LESSON state line not found exactly once.")
src2 = src2.replace(old_state, old_state + "\n(CASESTUDY_SEARCH, CASESTUDY_EXTRA) = range(40, 42)", 1)

# 2) _build_case_study_context() ফাংশন যোগ করা (helper keyboard-এর ঠিক আগে)
anchor_helper = "def _cslesson_next_keyboard() -> InlineKeyboardMarkup:"
if src2.count(anchor_helper) != 1:
    sys.exit("ABORT: _cslesson_next_keyboard anchor not found once.")

context_fn = '''def _build_case_study_context(patient_id: str) -> str | None:
    """রোগীর Chief Complaint + Assessment + সাম্প্রতিক Treatment Note + Report লিস্ট
    একত্র করে Case Study AI-কে দেওয়ার জন্য একটা সংক্ষিপ্ত context বানায়।"""
    patient = sheets.get_patient_by_id(patient_id)
    if patient is None:
        return None

    name = patient.get("Full_Name") or patient.get("Name") or "Unknown"
    lines = [f"রোগী: {name} ({patient_id})"]

    problem = patient.get("Note") or patient.get("Notes") or patient.get("Problem", "")
    if problem:
        lines.append(f"প্রাথমিক সমস্যা/নোট: {problem}")

    assessments = sheets.get_assessments_for_patient(patient_id)
    if assessments:
        latest = assessments[0]
        category = latest.get("Category", "")
        test_data = latest.get("Test_Data", {}) or {}
        chief_complaint = test_data.get("ChiefComplaint", "")
        lines.append(f"\\nAssessment Category: {category}")
        if chief_complaint:
            lines.append(f"Chief Complaint: {chief_complaint}")
        for k, v in test_data.items():
            if k == "ChiefComplaint" or not v:
                continue
            lines.append(f"  {k}: {v}")
    else:
        lines.append("\\nকোনো Assessment রেকর্ড নেই।")

    treatment_notes = sheets.get_treatment_notes_for_patient(patient_id)
    if treatment_notes:
        lines.append("\\nসাম্প্রতিক ট্রিটমেন্ট নোট:")
        for t in treatment_notes[-3:]:
            date_str = t.get("Date", "")
            note_text = t.get("Note", "") or t.get("Notes", "") or t.get("Treatment_Given", "") or t.get("Remarks", "")
            if note_text:
                lines.append(f"  • {date_str}: {note_text}")

    reports = sheets.get_reports_for_patient(patient_id)
    if reports:
        lines.append("\\nআপলোড করা রিপোর্ট/ফাইল:")
        for r in reports[-5:]:
            fname = r.get("File_Name", "")
            ftype = r.get("File_Type", "")
            if fname:
                lines.append(f"  • {fname} ({ftype})")

    full_text = "\\n".join(lines)
    if len(full_text) > 3000:
        full_text = full_text[:2990] + "\\n...(আরও আছে)"
    return full_text


'''
src2 = src2.replace(anchor_helper, context_fn + anchor_helper, 1)

# 3) casestudy_start / casestudy_receive / casestudy_lesson_callback পুরোটা replace
start_fn = "async def casestudy_start(update, context):"
end_fn = "async def casestudy_cancel(update, context):"
si = src2.find(start_fn)
ei = src2.find(end_fn)
if si == -1 or ei == -1 or ei <= si:
    sys.exit("ABORT: casestudy_start/casestudy_cancel boundary not found.")

new_fns = '''async def casestudy_start(update, context):
    staff = context.user_data.get("staff") or await _require_staff(update, context)
    if staff is None:
        return ConversationHandler.END
    if not roles.can_access(staff.get("Role", ""), roles.MENU_CASE_STUDY):
        return ConversationHandler.END
    await update.message.reply_text(
        "\\U0001F4DA কোন রোগীর কেস পড়াবে? নাম, ফোন নম্বর, অথবা Patient ID লেখো।\\n"
        "বাতিল করতে /cancel লেখো।"
    )
    return CASESTUDY_SEARCH


async def casestudy_search_receive(update, context):
    query_text = update.message.text.strip()
    results = sheets.search_patients(query_text)
    if not results:
        await update.message.reply_text("কোনো রোগী পাওয়া যায়নি। আবার চেষ্টা করো, অথবা /cancel দাও।")
        return CASESTUDY_SEARCH
    results = results[:10]
    await update.message.reply_text(
        "কোন রোগীর কেস পড়াবে?",
        reply_markup=_patient_search_buttons(results, "cssel_", "cssearchback"),
    )
    return CASESTUDY_SEARCH


async def casestudy_select_callback(update, context):
    query = update.callback_query
    await query.answer()
    patient_id = query.data.replace("cssel_", "", 1)

    case_context = _build_case_study_context(patient_id)
    if case_context is None:
        await query.edit_message_text("রোগী পাওয়া যায়নি।")
        return ConversationHandler.END

    context.user_data["cs_case_context"] = case_context
    await query.edit_message_text(
        "\\u2705 রোগীর ডেটা লোড হয়েছে।\\n"
        "কেসের বাড়তি কোনো তথ্য/অবজারভেশন থাকলে লেখো, না থাকলে শুধু 'না' লিখো।"
    )
    return CASESTUDY_EXTRA


async def casestudy_search_cancel_callback(update, context):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("\\u274c বাতিল করা হলো।")
    return ConversationHandler.END


async def casestudy_extra_receive(update, context):
    text = update.message.text.strip()
    case_context = context.user_data.get("cs_case_context", "")
    extra = "" if text in ("না", "না।", "no", "No", "No.") else text
    case_text = case_context + (f"\\n\\nবাড়তি তথ্য: {extra}" if extra else "")

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

# 4) ConversationHandler registration replace
start_conv = "casestudy_conv = ConversationHandler("
end_conv = "app.add_handler(casestudy_conv)"
si2 = src2.find(start_conv)
ei2 = src2.find(end_conv)
if si2 == -1 or ei2 == -1 or ei2 <= si2:
    sys.exit("ABORT: casestudy_conv registration boundary not found.")
ei2_end = ei2 + len(end_conv)

new_conv = '''casestudy_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex(f"^{roles.MENU_CASE_STUDY}$"), casestudy_start)
        ],
        states={
            CASESTUDY_SEARCH: [
                CallbackQueryHandler(casestudy_select_callback, pattern="^cssel_"),
                CallbackQueryHandler(casestudy_search_cancel_callback, pattern="^cssearchback$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_search_receive),
            ],
            CASESTUDY_EXTRA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_extra_receive)
            ],
            CASESTUDY_LESSON: [
                CallbackQueryHandler(casestudy_lesson_callback, pattern="^cslesson_next$")
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
