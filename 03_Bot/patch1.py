# -*- coding: utf-8 -*-
import sys

path1 = "case_study_ai.py"
with open(path1, "r", encoding="utf-8") as f:
    src1 = f.read()

if "def answer_case_lesson" in src1:
    print("case_study_ai.py: already patched (answer_case_lesson exists) — skip")
else:
    if "def answer_case_study(case_text: str) -> str:" not in src1:
        sys.exit("ABORT: case_study_ai.py — original answer_case_study() function paini.")

    addition = r'''

LESSON_TITLES = [
    "Lesson 1: Case Summary, Chief Complaint, History Taking, Red Flags Screening, Clinical Reasoning, Possible Diagnosis, Differential Diagnosis",
    "Lesson 2: Anatomy + Biomechanics + Pathophysiology (Bone, Joint, Muscle, Ligament, Tendon, Fascia, Nerve, Blood Supply, Dermatome, Myotome)",
    "Lesson 3: Clinical Assessment (Subjective/Objective Exam, Observation, Palpation, ROM, MMT, Neurological Exam, Special Tests, Functional Assessment, Outcome Measures)",
    "Lesson 4: Investigation (Radiology, Blood Test, EMG, NCS, ICF Diagnosis, Problem List, Goal Setting, Prognosis)",
    "Lesson 5: Evidence-Based Treatment (Pain Management, Manual Therapy, Exercise Therapy, Neural Mobilization, Balance/Gait/Functional Training, Patient Education)",
    "Lesson 6: Electrotherapy (per-modality when/when-not, parameters, contraindications, evidence)",
    "Lesson 7: Home Exercise Program (Daily Plan, Weekly Progression, Ergonomic Advice)",
    "Lesson 8: Viva (কমপক্ষে ৩০টি প্রশ্ন, উত্তরসহ, Clinical Tips)",
    "Lesson 9: MCQ (কমপক্ষে ৩০টি, উত্তরসহ)",
    "Lesson 10: OSPE (Practical Exam, Examiner Questions, Clinical Pearls, Common Mistakes, Evidence Update, Learning Summary, Top 10 Take Home Message)",
]

LESSON_SYSTEM_PROMPT = """তুমি একজন Senior Physiotherapy Professor, Clinical Instructor, Evidence-Based Physiotherapist এবং Mentor। তোমার কাছে Bachelor of Physiotherapy (BPT)-এর সম্পূর্ণ ৪ বছরের সিলাবাস, আধুনিক Clinical Practice Guideline এবং Evidence-Based Physiotherapy সম্পর্কিত জ্ঞান রয়েছে।

ব্যবহারকারী একটা রোগীর Case দিয়েছে। তাকে এখন একটা নির্দিষ্ট Lesson (ইউজার মেসেজে বলা থাকবে কোনটা) শেখাতে হবে।

নিয়ম:
- শুধু যে Lesson চাওয়া হয়েছে, শুধু সেটাই লেখো। অন্য কোনো Lesson বা তার কন্টেন্ট লিখো না।
- শুধু Case-এর সাথে সম্পর্কিত বিষয় শেখাও।
- Investigation Lesson-এ: কোনো অবস্থাতেই অপ্রয়োজনীয় Investigation লিখো না। History ও Physical Exam দিয়ে Diagnosis সম্ভব হলে Investigation লিখো না। শুধু তখনই দাও যখন Diagnosis নিশ্চিত করতে হবে / Red Flag আছে / Serious pathology সন্দেহ / Surgery বিবেচনায় আছে / চিকিৎসার সিদ্ধান্ত বদলাতে পারে। প্রয়োজন না হলে স্পষ্ট লিখো "বর্তমান Clinical Findings অনুযায়ী অতিরিক্ত Investigation প্রয়োজন নেই।" Routine MRI/CT/X-ray/Blood Test দিও না।
- Treatment/Electrotherapy Lesson-এ: অপ্রয়োজনীয় কিছু লিখো না, শুধু প্রয়োজনীয়টুকু, প্রতিটির জন্য কেন/কীভাবে/কতবার/Evidence।
- রোগীর আর্থিক অবস্থা বিবেচনা করো। যত কম Test করে নিরাপদ Diagnosis করা যায় সেই নীতি অনুসরণ করো।
- International Evidence-Based Guideline (APTA, NICE, IFOMPT, WHO) অনুসরণ করো।
- Clinical Reasoning সবসময় ব্যাখ্যা করো।
- বাংলায় শেখাও, Medical Terms ইংরেজিতে রাখো।
- ক্লাসে শিক্ষক যেমন বুঝান তেমনভাবে লিখো, Telegram মেসেজ আকারে (heavy markdown ছাড়া, সাধারণ বুলেট ঠিক আছে)।
- Patient Safety সর্বোচ্চ অগ্রাধিকার। কোনো তথ্য বানিয়ে লিখো না — নিশ্চিত না হলে স্পষ্ট বলো।
- Lesson শেষে ইউজারকে বলা নির্দেশনা (পরের Lesson দেখতে "দাও" লিখতে বলা, বা শেষ Lesson হলে সমাপ্তির লাইন) ইউজার মেসেজেই বলে দেওয়া থাকবে, সেটা হুবহু লিখে দাও।"""


def answer_case_lesson(case_text: str, lesson_number: int) -> str:
    if not OPENROUTER_API_KEY:
        return "⚠️ OPENROUTER_API_KEY সেট করা নেই। .env / Render env var চেক করো।"

    title = LESSON_TITLES[lesson_number - 1]
    user_msg = (
        f"রোগীর কেস: {case_text}\n\n"
        f"এখন এই Lesson-টা লিখে দাও: {title}\n"
        "শুধু এই Lesson-টাই লিখো, অন্য কোনো Lesson বা ভূমিকা/উপসংহার যোগ কোরো না। আগের কোনো Lesson পুনরাবৃত্তি কোরো না।"
    )
    if lesson_number < len(LESSON_TITLES):
        user_msg += "\n\nএই Lesson-এর একদম শেষে হুবহু এই লাইনটা লিখো: \"পরবর্তী Lesson দেখতে শুধু 'দাও' লিখুন।\""
    else:
        user_msg += "\n\nএই Lesson-এর একদম শেষে হুবহু এই লাইনটা লিখো: \"এই Case Study সম্পূর্ণ শেষ হয়েছে। নতুন Case দিতে পারেন।\""

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
                    {"role": "system", "content": LESSON_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 2000,
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"⚠️ AI থেকে উত্তর আনতে সমস্যা হয়েছে: {e}"
'''
    src1 = src1 + addition
    with open(path1, "w", encoding="utf-8") as f:
        f.write(src1)
    print("case_study_ai.py: patched OK")

path2 = "bot.py"
with open(path2, "r", encoding="utf-8") as f:
    src2 = f.read()

if "CASESTUDY_LESSON" in src2:
    print("bot.py: already patched (CASESTUDY_LESSON exists) — skip")
else:
    old_state = "(CASESTUDY_INPUT,) = range(38, 39)"
    c = src2.count(old_state)
    if c != 1:
        sys.exit(f"ABORT: bot.py state line — {c} matches found (expected 1). File drift.")
    src2 = src2.replace(old_state, old_state + "\n(CASESTUDY_LESSON,) = range(39, 40)", 1)

    old_receive = '''async def casestudy_receive(update, context):
    staff = context.user_data.get("staff", {})
    case_text = update.message.text.strip()
    await update.message.reply_text("\U0001F914 কেস বিশ্লেষণ করছি...")
    answer = case_study_ai.answer_case_study(case_text)
    await update.message.reply_text(
        answer,
        reply_markup=_menu_keyboard(staff.get("Role", "")),
    )
    return ConversationHandler.END'''
    c = src2.count(old_receive)
    if c != 1:
        sys.exit(f"ABORT: bot.py casestudy_receive() — {c} matches found (expected 1). File drift.")

    new_receive = '''async def casestudy_receive(update, context):
    staff = context.user_data.get("staff", {})
    case_text = update.message.text.strip()
    context.user_data["cs_case_text"] = case_text
    context.user_data["cs_lesson"] = 1
    await update.message.reply_text("\U0001F914 কেস বিশ্লেষণ করছি, Lesson 1 তৈরি হচ্ছে...")
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
    await update.message.reply_text(f"\U0001F914 Lesson {lesson} তৈরি হচ্ছে...")
    answer = case_study_ai.answer_case_lesson(case_text, lesson)
    context.user_data["cs_lesson"] = lesson

    if lesson >= len(case_study_ai.LESSON_TITLES):
        await update.message.reply_text(
            answer,
            reply_markup=_menu_keyboard(staff.get("Role", "")),
        )
        return ConversationHandler.END

    await update.message.reply_text(answer)
    return CASESTUDY_LESSON'''
    src2 = src2.replace(old_receive, new_receive, 1)

    old_states = '''        states={
            CASESTUDY_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(_ALL_MENU_REGEX), casestudy_receive)
            ],
        },
        fallbacks=[
            MessageHandler(filters.Regex(_ALL_MENU_REGEX), _cancel_on_menu_press),
            CommandHandler("cancel", casestudy_cancel),
            CommandHandler("start", _restart_via_start),
        ],
    )
    app.add_handler(casestudy_conv)'''
    c = src2.count(old_states)
    if c != 1:
        sys.exit(f"ABORT: bot.py casestudy_conv states block — {c} matches found (expected 1). File drift.")

    new_states = '''        states={
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
    src2 = src2.replace(old_states, new_states, 1)

    with open(path2, "w", encoding="utf-8") as f:
        f.write(src2)
    print("bot.py: patched OK")

print("DONE")
