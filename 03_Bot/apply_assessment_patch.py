import sys

def replace_once(text, old, new, filename):
    n = text.count(old)
    if n != 1:
        print(f"❌ {filename}: anchor {n} বার পাওয়া গেছে (দরকার ১ বার) — প্যাচ বাতিল।")
        sys.exit(1)
    return text.replace(old, new, 1)


# ---------------- config.py ----------------
with open("config.py", "r", encoding="utf-8") as f:
    c = f.read()
c = replace_once(
    c,
    'SHEET_TREATMENT_PLANS = "12_Treatment_Plans"',
    'SHEET_TREATMENT_PLANS = "12_Treatment_Plans"\nSHEET_ASSESSMENTS = "10_Assessments"',
    "config.py",
)
with open("config.py", "w", encoding="utf-8") as f:
    f.write(c)
print("config.py ✅")


# ---------------- sheets.py ----------------
with open("sheets.py", "r", encoding="utf-8") as f:
    s = f.read()

s = replace_once(s, "import gspread", "import json\nimport gspread", "sheets.py (import)")

new_funcs = '''def _next_assessment_id(ws) -> str:
    ids = ws.col_values(1)[1:]
    numbers = []
    for v in ids:
        if v.startswith("AS"):
            try:
                numbers.append(int(v[2:]))
            except ValueError:
                pass
    next_num = (max(numbers) + 1) if numbers else 1
    return f"AS{next_num:04d}"


def add_assessment(patient_id: str, category: str, test_data: dict, created_by: str) -> str:
    """10_Assessments \u09b6\u09c0\u099f\u09c7 \u09aa\u09cd\u09b0\u09be\u09a5\u09ae\u09bf\u0995 \u09ae\u09c2\u09b2\u09cd\u09af\u09be\u09df\u09a8\u09c7\u09b0 \u09ab\u09b2\u09be\u09ab\u09b2 \u09b8\u09c7\u09ad \u0995\u09b0\u09c7 (\u099f\u09c7\u09b8\u09cd\u099f-\u09b0\u09c7\u099b\u09be\u09b2\u09cd\u099f JSON \u0986\u0995\u09be\u09b0\u09c7,\n    \u0995\u09be\u09b0\u09a3 \u09aa\u09cd\u09b0\u09a4\u09bf\u099f\u09be category-\u09b0 \u099f\u09c7\u09b8\u09cd\u099f \u0986\u09b2\u09be\u09a6\u09be \u2014 \u0986\u09b2\u09be\u09a6\u09be \u0995\u09b2\u09be\u09ae \u09ac\u09be\u09a8\u09be\u09b2\u09c7 \u09b6\u09c0\u099f \u098f\u09b2\u09cb\u09ae\u09c7\u09b2\u09cb \u09b9\u09df\u09c7 \u09af\u09c7\u09a4)."""
    ws = _worksheet(config.SHEET_ASSESSMENTS)
    assessment_id = _next_assessment_id(ws)
    now = bd_now()
    row = [
        assessment_id,
        patient_id,
        category,
        json.dumps(test_data, ensure_ascii=False),
        created_by,
        now.strftime("%Y-%m-%d %I:%M %p"),
    ]
    ws.append_row(row, value_input_option="RAW")
    return assessment_id


def get_assessments_for_patient(patient_id: str) -> list[dict]:
    """\u098f\u0995\u099c\u09a8 \u09b0\u09cb\u0997\u09c0\u09b0 \u09b8\u09ac \u09aa\u09cd\u09b0\u09be\u09a5\u09ae\u09bf\u0995 \u09ae\u09c2\u09b2\u09cd\u09af\u09be\u09df\u09a8 \u09b0\u09c7\u0995\u09b0\u09cd\u09a1 \u09ab\u09c7\u09b0\u09a4 \u09a6\u09c7\u09df (\u09a8\u09a4\u09c1\u09a8 \u09a5\u09c7\u0995\u09c7 \u09aa\u09c1\u09b0\u09a8\u09cb), Test_Data \u09a1\u09bf\u0995\u09cb\u09a1 \u0995\u09b0\u09c7\u0964"""
    ws = _worksheet(config.SHEET_ASSESSMENTS)
    records = safe_get_all_records(ws)
    out = []
    for r in records:
        if str(r.get("Patient_ID", "")).strip() == patient_id.strip():
            r = dict(r)
            try:
                r["Test_Data"] = json.loads(r.get("Test_Data", "") or "{}")
            except (json.JSONDecodeError, TypeError):
                r["Test_Data"] = {}
            out.append(r)
    return list(reversed(out))


def add_treatment_plan(data: dict, created_by: str) -> str:'''

s = replace_once(s, "def add_treatment_plan(data: dict, created_by: str) -> str:", new_funcs, "sheets.py (add_assessment)")

with open("sheets.py", "w", encoding="utf-8") as f:
    f.write(s)
print("sheets.py ✅")


# ---------------- bot.py ----------------
with open("bot.py", "r", encoding="utf-8") as f:
    b = f.read()

b = replace_once(b, "import ai_helper", "import ai_helper\nimport assessment_defs", "bot.py (import)")

b = replace_once(
    b,
    "(STAFFAI_QUESTION,) = range(37, 38)",
    "(STAFFAI_QUESTION,) = range(37, 38)\n\nTPLAN_CATEGORY, TPLAN_TESTS = range(200, 202)",
    "bot.py (states)",
)

helper_block = '''def _category_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(assessment_defs.ASSESSMENT_CATEGORIES[k]["label"], callback_data=f"tpcat_{k}")]
        for k in assessment_defs.CATEGORY_ORDER
    ]
    return InlineKeyboardMarkup(buttons)


async def _assessment_advance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """assessment queue \u09a5\u09c7\u0995\u09c7 \u09aa\u09b0\u09c7\u09b0 \u099f\u09c7\u09b8\u09cd\u099f \u09aa\u09be\u09a0\u09be\u09df; queue \u09b6\u09c7\u09b7 \u09b9\u09b2\u09c7 \u09b8\u09c7\u09ad \u0995\u09b0\u09c7 \u09aa\u09c1\u09b0\u09a8\u09cb Diagnosis \u09a7\u09be\u09aa\u09c7 \u099a\u09b2\u09c7 \u09af\u09be\u09df\u0964"""
    send = update.message.reply_text if update.message else update.callback_query.message.reply_text
    queue = context.user_data.get("assessment_queue", [])

    if not queue:
        t = context.user_data.get("tplan", {})
        category = context.user_data.get("assessment_category", "")
        answers = context.user_data.get("assessment_answers", {})
        staff = context.user_data.get("staff", {})
        try:
            sheets.add_assessment(
                t.get("Patient_ID", ""), category, answers,
                created_by=staff.get("Full_Name", "Unknown"),
            )
        except Exception:
            logger.exception("_assessment_advance: assessment \u09b8\u09c7\u09ad \u0995\u09b0\u09a4\u09c7 \u09ac\u09cd\u09af\u09b0\u09cd\u09a5 \u09b9\u09df\u09c7\u099b\u09c7")
        context.user_data.pop("assessment_queue", None)
        context.user_data.pop("assessment_current", None)
        context.user_data.pop("assessment_answers", None)
        context.user_data.pop("assessment_category", None)

        prev = context.user_data.get("tplan_prev", {})
        prev_diag = prev.get("Diagnosis", "")
        hint = f" (\u0986\u0997\u09c7\u09b0\u099f\u09be: {prev_diag} \u2014 \u098f\u0995\u0987 \u09b0\u09be\u0996\u09a4\u09c7 - \u09a6\u09be\u0993)" if prev_diag else ""
        await send(
            f"\u2705 \u09aa\u09cd\u09b0\u09be\u09a5\u09ae\u09bf\u0995 \u09ae\u09c2\u09b2\u09cd\u09af\u09be\u09df\u09a8 \u09b8\u09ae\u09cd\u09aa\u09a8\u09cd\u09a8 \u09b9\u09df\u09c7\u099b\u09c7\u0964\\n\\n\u09b8\u09ae\u09b8\u09cd\u09af\u09be/\u09aa\u09b0\u09cd\u09af\u09ac\u09c7\u0995\u09cd\u09b7\u09a3 (Diagnosis) \u09b2\u09c7\u0996\u09cb{hint}:",
            reply_markup=_skip_keyboard() if prev_diag else ReplyKeyboardRemove(),
        )
        return TPLAN_DIAGNOSIS

    test = queue.pop(0)
    context.user_data["assessment_queue"] = queue
    context.user_data["assessment_current"] = test
    if test["type"] == "buttons":
        buttons = [
            [InlineKeyboardButton(opt, callback_data=f"atest_{test['key']}__{opt}")]
            for opt in test["options"]
        ]
        await send(test["label"], reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await send(test["label"], reply_markup=ReplyKeyboardRemove())
    return TPLAN_TESTS


async def tplan_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Chief Complaint \u0995\u09cd\u09af\u09be\u099f\u09be\u0997\u09b0\u09bf \u09ac\u09be\u099b\u09be\u0987 \u0995\u09b0\u09b2\u09c7 \u09b8\u09c7\u0987 category-\u09b0 \u099f\u09c7\u09b8\u09cd\u099f-queue \u09a4\u09c8\u09b0\u09bf \u0995\u09b0\u09c7 assessment \u09b6\u09c1\u09b0\u09c1 \u0995\u09b0\u09c7\u0964"""
    query = update.callback_query
    await query.answer()
    key = query.data.replace("tpcat_", "", 1)
    category = assessment_defs.ASSESSMENT_CATEGORIES.get(key)
    if not category:
        return TPLAN_CATEGORY
    context.user_data["assessment_category"] = key
    context.user_data["assessment_queue"] = list(category["tests"])
    context.user_data["assessment_answers"] = {}
    await query.edit_message_text(
        f"\u2705 \u0995\u09cd\u09af\u09be\u099f\u09be\u0997\u09b0\u09bf \u09ac\u09be\u099b\u09be\u0987 \u09b9\u09df\u09c7\u099b\u09c7: {category['label']}\\n\\n\u09aa\u09cd\u09b0\u09be\u09a5\u09ae\u09bf\u0995 \u09ae\u09c2\u09b2\u09cd\u09af\u09be\u09df\u09a8 \u09b6\u09c1\u09b0\u09c1 \u09b9\u099a\u09cd\u099b\u09c7..."
    )
    return await _assessment_advance(update, context)


async def atest_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """assessment-\u098f\u09b0 \u09ac\u09be\u099f\u09a8-\u09ad\u09bf\u09a4\u09cd\u09a4\u09bf\u0995 \u099f\u09c7\u09b8\u09cd\u099f\u09c7\u09b0 \u0989\u09a4\u09cd\u09a4\u09b0 \u09b0\u09c7\u0995\u09b0\u09cd\u09a1 \u0995\u09b0\u09c7 \u09aa\u09b0\u09c7\u09b0 \u099f\u09c7\u09b8\u09cd\u099f\u09c7 \u09af\u09be\u09df\u0964"""
    query = update.callback_query
    await query.answer()
    payload = query.data.replace("atest_", "", 1)
    key, _, value = payload.partition("__")
    current = context.user_data.get("assessment_current")
    if not current or current.get("key") != key:
        return TPLAN_TESTS
    answers = context.user_data.setdefault("assessment_answers", {})
    answers[key] = value
    await query.edit_message_text(f"{current['label']}\\n\u27a1\ufe0f {value}")
    return await _assessment_advance(update, context)


async def atest_text_receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """assessment-\u098f\u09b0 \u099f\u09c7\u0995\u09cd\u09b8\u099f-\u09ad\u09bf\u09a4\u09cd\u09a4\u09bf\u0995 \u099f\u09c7\u09b8\u09cd\u099f\u09c7\u09b0 \u0989\u09a4\u09cd\u09a4\u09b0 \u09b0\u09c7\u0995\u09b0\u09cd\u09a1 \u0995\u09b0\u09c7 \u09aa\u09b0\u09c7\u09b0 \u099f\u09c7\u09b8\u09cd\u099f\u09c7 \u09af\u09be\u09df\u0964"""
    current = context.user_data.get("assessment_current")
    if not current or current.get("type") != "text":
        return TPLAN_TESTS
    answers = context.user_data.setdefault("assessment_answers", {})
    answers[current["key"]] = update.message.text.strip()
    return await _assessment_advance(update, context)


async def tplan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):'''

b = replace_once(
    b,
    "async def tplan_start(update: Update, context: ContextTypes.DEFAULT_TYPE):",
    helper_block,
    "bot.py (helper block)",
)

# Bengali বাক্য সরাসরি Python escape দিয়ে টাইপ করলে Unicode normalization (NFC/NFD)
# mismatch হয়ে exact-match ফেইল করতে পারে (যেমন "য়" একাধিকভাবে এনকোড হয়) — তাই এই অংশটা
# pure-ASCII মার্কার দিয়ে বাউন্ড করে স্লাইস-রিপ্লেস করা হচ্ছে, কোনো Bengali old_str ম্যাচ করা হচ্ছে না।
start_marker = 'context.user_data["tplan_prev"] = last_plan or {}\n'
end_marker = "async def tplan_diagnosis(update: Update, context: ContextTypes.DEFAULT_TYPE):"
if b.count(start_marker) != 1 or b.count(end_marker) != 1:
    print("❌ bot.py (select_callback tail): ASCII বাউন্ডারি মার্কার ঠিক ১ বার পাওয়া যায়নি — প্যাচ বাতিল।")
    sys.exit(1)
start_idx = b.index(start_marker) + len(start_marker)
end_idx = b.index(end_marker)

new_middle = '''    await query.edit_message_text(
        f"{warn}\u2705 \u09b0\u09cb\u0997\u09c0 \u09ac\u09be\u099b\u09be\u0987 \u09b9\u09b2\u09cb: {patient.get('Full_Name')} ({patient_id})"
    )
    await query.message.reply_text(
        "Chief Complaint \u0985\u09a8\u09c1\u09af\u09be\u09df\u09c0 \u0995\u09cd\u09af\u09be\u099f\u09be\u0997\u09b0\u09bf \u09ac\u09be\u099b\u09be\u0987 \u0995\u09b0\u09cb \u2014 \u098f\u09b0 \u09ad\u09bf\u09a4\u09cd\u09a4\u09bf\u09a4\u09c7 \u09aa\u09cd\u09b0\u09be\u09a5\u09ae\u09bf\u0995 \u09ae\u09c2\u09b2\u09cd\u09af\u09be\u09df\u09a8 (assessment) \u09a8\u09c7\u0993\u09df\u09be \u09b9\u09ac\u09c7:",
        reply_markup=_category_keyboard(),
    )
    return TPLAN_CATEGORY


'''

b = b[:start_idx] + new_middle + b[end_idx:]
print("bot.py (select_callback tail) ✅ (ASCII-slice দিয়ে প্যাচ হয়েছে)")

old_states = '''            TPLAN_DIAGNOSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_diagnosis)],'''
new_states = '''            TPLAN_CATEGORY: [
                CallbackQueryHandler(tplan_category_callback, pattern="^tpcat_"),
            ],
            TPLAN_TESTS: [
                CallbackQueryHandler(atest_callback, pattern="^atest_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), atest_text_receive),
            ],
            TPLAN_DIAGNOSIS: [MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), tplan_diagnosis)],'''

b = replace_once(b, old_states, new_states, "bot.py (conv states registration)")

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(b)
print("bot.py ✅")

print("\n✅✅ সব প্যাচ সফলভাবে প্রয়োগ হয়েছে।")
