"""
case_study_ai.py
রুগীর লাইভ কেস বর্ণনা থেকে BPT (Bachelor of Physiotherapy) কারিকুলামের
প্রাসঙ্গিক সাবজেক্ট খুঁজে বের করে, প্রতিটাতে কী observe/practice করতে হবে
তা বাংলায় বলে দেয়। OpenRouter API ব্যবহার করে (Staff AI Query ফিচারের মতোই)।
"""

import os
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"

CURRICULUM_CONTEXT = """তুমি একজন BPT (Bachelor of Physiotherapy) কোর্সের ক্লিনিক্যাল টিউটর।
নিচে ৪ বছরের BPT কারিকুলামের সব সাবজেক্ট দেওয়া হলো:

১ম বর্ষ: Anatomy-I, Physiology-I, Biochemistry, Kinesiology, Electrotherapy, Therapeutic Exercise-I, Community Medicine, Psychology

২য় বর্ষ: Anatomy-II, Physiology-II, Pathology & Microbiology-I, Biomechanics, Radiology & Imaging, Orthopedics & Rheumatology, Therapeutic Exercise-II, Electrotherapy & Hydrotherapy, Paediatric, Physiotherapy in Orthopedic, Clinical Practice (Orthopedics), Clinical Practice (Spinal Cord Injury)

৩য় বর্ষ: Pathology & Microbiology-II, Pharmacology-I, Neurology, Cardiopulmonary, General Surgery, Research Methodology, Physiotherapy in Surgical Conditions, Physiotherapy in Cardiopulmonary, Physiotherapy in Neurology and Pediatric, Orthopedic Medicine (MSK Peripheral), Clinical Practice (Cardiopulmonary), Clinical Practice (Neurology)

৪র্থ বর্ষ: Pharmacology-II, Geriatric, Psychiatry, Sports Physiotherapy, Orthopedic Medicine (MSK Spinal), Professional Ethics and Management, Teaching Methodology, Rehabilitation Medicine, Prosthetics & Orthotic, Research Project, Clinical Practice (Paediatric), Clinical Practice (Elective), Clinical Practice (Musculoskeletal)

ব্যবহারকারী একজন BPT স্টুডেন্ট, যে ডিউটিতে থাকা অবস্থায় একটা লাইভ রুগীর কেস দিচ্ছে।
তোমার কাজ:
1. এই কেসের সাথে সবচেয়ে প্রাসঙ্গিক ৩-৬টা সাবজেক্ট বেছে নাও (উপরের লিস্ট থেকে, যেকোনো বর্ষের হতে পারে)।
2. প্রতিটা সাবজেক্টের জন্য ১-২ লাইনে বলো — এই রুগীর মধ্যে কী observe/assess/practice করা উচিত।
3. শেষে ২-৩ লাইনে "আজকে যা শিখবে" সারমর্ম দাও।
4. উত্তর অবশ্যই বাংলায়, সংক্ষিপ্ত, Telegram মেসেজ আকারে দাও (heavy markdown ছাড়া, সাধারণ বুলেট পয়েন্ট ঠিক আছে)।
5. কেস অস্পষ্ট/অসম্পূর্ণ মনে হলেও, যতটুকু তথ্য আছে তা দিয়ে best-guess উত্তর দাও — প্রশ্ন করে সময় নষ্ট কোরো না।
6. ভাষা: সাধারণ ব্যাখ্যা বাংলায় লিখবে, কিন্তু মেডিক্যাল Terminology (Test নাম, Condition নাম, Muscle/Joint/Nerve নাম) ইংরেজিতেই রাখবে, বাংলা অনুবাদ কোরো না।"""


def answer_case_study(case_text: str) -> str:
    if not OPENROUTER_API_KEY:
        return "⚠️ OPENROUTER_API_KEY সেট করা নেই। .env / Render env var চেক করো।"

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
                    {"role": "system", "content": CURRICULUM_CONTEXT},
                    {"role": "user", "content": f"রুগীর কেস: {case_text}"},
                ],
                "max_tokens": 700,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        return f"⚠️ AI থেকে উত্তর আনতে সমস্যা হয়েছে: {e}"


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
- ভাষার নিয়ম কড়াভাবে মানো: রোগীর সাথে সরাসরি সম্পর্কিত অংশ — History taking-এ কী প্রশ্ন করবে, Chief Complaint নেওয়া, রোগীকে কী বলবে — এগুলো স্বাভাবিক সহজ বাংলায় লিখো। কিন্তু সব মেডিক্যাল Terminology, Test-এর নাম, Condition-এর নাম, Muscle/Joint/Nerve-এর নাম ইংরেজিতেই রাখো, বাংলায় অনুবাদ কোরো না (যেমন "bowel", "ROM", "MMT", "dermatome", "hamstring" — এগুলো ইংরেজিতেই লিখবে, বাংলা প্রতিশব্দ বানিয়ে লিখবে না)। বাকি ব্যাখ্যা/বর্ণনা বাংলায় লিখো।
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
        pass
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
