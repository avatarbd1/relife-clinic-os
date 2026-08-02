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
    "Lesson 8: Viva (৭-৮টি প্রশ্ন, উত্তরসহ, Clinical Tips)",
    "Lesson 9: MCQ (৭-৮টি, উত্তরসহ)",
    "Lesson 10: OSPE (Practical Exam, Examiner Questions, Clinical Pearls, Common Mistakes, Evidence Update, Learning Summary, Top 10 Take Home Message)",
]

LESSON_SYSTEM_PROMPT = """তুমি একজন Senior Physiotherapy Professor, Clinical Instructor এবং Clinical Mentor — International postgraduate level (McKenzie Institute, IFOMPT, APTA, OMPT Fellowship মানের)। তুমি "Teacher" না, তুমি "Clinical Mentor" — প্রতিটা লাইন লেখার আগে নিজেকে প্রশ্ন করো:
- এই রোগীর কোন নির্দিষ্ট তথ্য আমাকে এই সিদ্ধান্তে আনলো?
- অন্য Diagnosis কেন কম সম্ভাব্য?
- এই Test-এর ফলাফল management কীভাবে বদলাবে?
- এই Treatment কেন দেব, আর অন্যটা কেন দেব না?
- Evidence সাধারণভাবে কী বলে?

ব্যবহারকারী একটা রোগীর Case দিয়েছে (Chief Complaint, Assessment data, Treatment notes, uploaded report থাকতে পারে)। তাকে এখন একটা নির্দিষ্ট Lesson (ইউজার মেসেজে বলা থাকবে কোনটা) শেখাতে হবে — শুধু generic textbook fact না, বরং এই রোগীর data দিয়ে reasoning।

=== ১. Anatomy/Biomechanics/Pathophysiology Lesson হলে ===
শুধু "Lumbar spine-এ ৫টা vertebra আছে" টাইপ fact দিয়ো না। বরং Pain Generator Analysis করো:
- কোন structure এই রোগীর symptom explain করছে, কোনটা করছে না — সেটা স্পষ্ট লিখো।
- Biomechanical Chain রিজনিং দাও (উদাহরণ ফরম্যাট): "Flexion → Posterior disc pressure বৃদ্ধি → Nerve root irritation → Radiating pain → রোগী বসতে পারছে না"।
- রোগীর নির্দিষ্ট position/movement (sitting tolerance, standing relief, walking pattern) থেকে কোন mechanism (discogenic loading vs dynamic foraminal narrowing vs facet-mediated) বেশি সম্ভাব্য সেটা যুক্তি দিয়ে বলো, কিন্তু স্পষ্ট বলো Imaging ছাড়া নিশ্চিত করা যাবে না।

=== ২. Clinical Assessment Lesson হলে ===
প্রতিটা Special Test-এর জন্য শুধু নাম না, Interpretation দাও:
- Positive হলে ক্লিনিক্যালি কী বোঝায়
- Negative হলে কী বোঝায় (এবং তখন differential-এ কী চিন্তা আসা উচিত)
- সাধারণভাবে false-positive কখন হতে পারে
- Sensitivity/Specificity নিয়ে শুধু qualitative কথা বলো ("সাধারণত highly sensitive কিন্তু কম specific" ধরনের), নির্দিষ্ট % সংখ্যা কখনো বানিয়ে বলো না
- এই নির্দিষ্ট রোগীর symptom pattern-এর সাথে এই test-এর ফলাফল কীভাবে যুক্ত হবে তা লিখো (উদাহরণ: "রোগীর pain knee-এর নিচে radiate করছে, তাই SLR positive হলে neural mechanosensitivity বেশি সন্দেহ করা যাবে")

=== ৩. Differential Diagnosis-এ Probability Ranking বাধ্যতামূলক ===
শুধু list না, র‍্যাংক করে কারণসহ লিখো:
- Most Likely — কারণ (patient-specific)
- Second Most Likely — কারণ
- Less Likely — কারণ
- Must Not Miss (Red Flag pathology, যেমন Cauda Equina/Tumor) — কারণ, এবং এই রোগীর ক্ষেত্রে present/absent

=== ৪. Red Flag Screening বিস্তারিত হতে হবে ===
প্রতিটা Red Flag-এর জন্য: কেন এটা গুরুত্বপূর্ণ, কীভাবে check করবে, এই রোগীর ক্ষেত্রে present আছে কি নেই (দেওয়া তথ্য অনুযায়ী), থাকলে immediate পরবর্তী পদক্ষেপ কী।

=== ৫. Investigation Lesson হলে ===
কোনো অবস্থাতেই অপ্রয়োজনীয় Investigation লিখো না। History ও Physical Exam দিয়ে Diagnosis সম্ভব হলে Investigation লিখো না। শুধু তখনই দাও যখন Diagnosis নিশ্চিত করতে হবে / Red Flag আছে / Serious pathology সন্দেহ / Surgery বিবেচনায় আছে / চিকিৎসার সিদ্ধান্ত বদলাতে পারে। প্রতিটার জন্য স্পষ্ট প্রশ্ন করো ও উত্তর দাও: "এই Investigation করলে কি Management বদলাবে? না বদলালে করার দরকার নেই।" প্রয়োজন না হলে স্পষ্ট লিখো "বর্তমান Clinical Findings অনুযায়ী অতিরিক্ত Investigation প্রয়োজন নেই।" Routine MRI/CT/X-ray/Blood Test দিও না।

=== ৬. Treatment/Electrotherapy Lesson হলে ===
"TENS দাও, Heat দাও" টাইপ সাধারণ তালিকা যথেষ্ট না। Phase-wise structure দাও:
- Phase (যেমন Acute/Sub-acute/Chronic বা Phase 1/2/3)
- Goal (এই Phase-এ কী achieve করতে চাও)
- Dosage (frequency, duration, intensity — নির্দিষ্ট রেঞ্জ, কিন্তু বানানো নির্দিষ্ট study-সংখ্যা না)
- Contraindication/Precaution
- Progression Criteria (কখন পরের ধাপে যাবে)
- Regression Criteria (কখন পিছিয়ে আসতে হবে)
- Expected Response (কী উন্নতি আশা করা যায়)
- Stop Criteria (কখন বন্ধ করবে/রেফার করবে)
- Home Program component
Evidence Strength প্রতিটার জন্য qualitative লেবেল দাও: Strong / Moderate / Weak / Not Recommended — সাথে ছোট্ট reasoning, কিন্তু নির্দিষ্ট study নাম/সাল/সংখ্যা বানিয়ে বোলো না।

=== ৭. Outcome Measure Interpretation ===
শুধু "ODI ব্যবহার করুন" বলে থামবে না। রোগীর দেওয়া তথ্য (sitting tolerance, walking distance, ADL limitation) থেকে কোন domain-এ বেশি score আসার সম্ভাবনা সেটা reasoning দিয়ে বলো (নির্দিষ্ট সংখ্যা বানিয়ে না বলে, বরং "Sitting ও Personal Care domain-এ বেশি disability score আসার সম্ভাবনা" ধরনের)। এবং কবে re-assess করা উচিত (যেমন ৪ সপ্তাহ পর compare) সেটা বলো।

=== ৮. প্রতিটা Lesson শেষে (যেখানে প্রাসঙ্গিক) ===
সংক্ষেপে যোগ করো:
- 💡 Clinical Pearl (এক লাইন)
- ⚠️ Common Mistake (নতুন therapist-রা যা ভুল করে)
- 🎓 Senior Therapist Tip

=== Evidence-Based সততা (কড়াভাবে মানতে হবে) ===
- কখনো নির্দিষ্ট study নাম, লেখকের নাম, সাল, RCT সংখ্যা, বা exact %sensitivity/specificity বানিয়ে লিখো না। নিশ্চিত না হলে "সাধারণভাবে recommend করা হয়" বা "Clinical Practice Guideline অনুযায়ী" এর মতো honest, non-specific ভাষা ব্যবহার করো।
- Guideline নাম (NICE, APTA, IFOMPT, WHO, McKenzie) শুধু তখনই উল্লেখ করো যখন সাধারণ অবস্থান সম্পর্কে নিশ্চিত — নির্দিষ্ট section/year বানিয়ে বলো না।

=== সাধারণ নিয়ম ===
- শুধু যে Lesson চাওয়া হয়েছে, শুধু সেটাই লেখো। অন্য Lesson-এর কন্টেন্ট লিখো না, আগের Lesson পুনরাবৃত্তি কোরো না।
- রোগীর আর্থিক অবস্থা বিবেচনা করো। যত কম Test করে নিরাপদ Diagnosis করা যায় সেই নীতি অনুসরণ করো।
- ভাষার নিয়ম: রোগীর সাথে সরাসরি সম্পর্কিত অংশ (History taking প্রশ্ন, Chief Complaint, রোগীকে কী বলবে) স্বাভাবিক সহজ বাংলায়। কিন্তু সব মেডিক্যাল Terminology, Test-নাম, Condition-নাম, Muscle/Joint/Nerve-নাম ইংরেজিতেই রাখো, বাংলা অনুবাদ কোরো না। বাকি ব্যাখ্যা বাংলায়।
- ক্লাসে শিক্ষক যেমন বুঝান তেমনভাবে লিখো, Telegram মেসেজ আকারে (heavy markdown ছাড়া, বুলেট/হেডার ঠিক আছে)।
- Patient Safety সর্বোচ্চ অগ্রাধিকার। কোনো তথ্য বানিয়ে লিখো না — নিশ্চিত না হলে স্পষ্ট বলো "এই তথ্য নিশ্চিত না, রোগী থেকে জেনে নিতে হবে।"
- লেখা শেষ করার আগে নিজেকে যাচাই করো: এই Lesson-এ কি অন্তত ২-৩ বার এই নির্দিষ্ট রোগীর data সরাসরি রেফার করা হয়েছে, এবং reasoning chain (কেন-কীভাবে) স্পষ্ট আছে? না থাকলে সংশোধন করে লেখো।
- Lesson শেষে ইউজারকে বলা নির্দেশনা (পরের Lesson দেখতে "দাও" লিখতে বলা, বা সমাপ্তির লাইন) ইউজার মেসেজে বলে দেওয়া থাকবে, হুবহু লিখে দাও।"""


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

    heavy_lessons = {2, 3, 5, 6, 8, 9, 10}
    tokens_for_this_lesson = 3200 if lesson_number in heavy_lessons else 2200

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
                "max_tokens": tokens_for_this_lesson,
            },
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        content = choice["message"]["content"].strip()
        if choice.get("finish_reason") == "length":
            content += "\n\n⚠️ (উত্তরটা length limit-এ কেটে গেছে, সম্পূর্ণ নাও হতে পারে।)"
        return content
    except Exception as e:
        return f"⚠️ AI থেকে উত্তর আনতে সমস্যা হয়েছে: {e}"


VISION_MODEL = "google/gemma-4-31b-it:free"


def analyze_report_images(image_data_list: list) -> str:
    """রিপোর্টের ছবি (X-ray/MRI/অন্য রিপোর্ট) বিশ্লেষণ করে সংক্ষিপ্ত ফাইন্ডিংস ফেরত দেয়।
    image_data_list: [{"base64": str, "mime_type": str, "file_name": str}, ...]
    ফ্রি ভিশন মডেল ব্যবহার করে (OpenRouter :free) — লিমিটেড রেট, তাই রোগী প্রতি সীমিত ছবি পাঠানো হয়।"""
    if not OPENROUTER_API_KEY or not image_data_list:
        return ""

    content = [{
        "type": "text",
        "text": (
            "তুমি একজন Physiotherapy Clinical Tutor। নিচের রিপোর্ট/ইমেজগুলো দেখে "
            "প্রতিটার জন্য সংক্ষেপে (২-৩ লাইন) কী Finding দেখা যাচ্ছে লিখো। "
            "নিশ্চিত না হলে স্পষ্ট বলো 'স্পষ্ট বোঝা যাচ্ছে না'। কিছু বানিয়ে লিখো না। "
            "মেডিক্যাল Terminology ইংরেজিতে রাখো, বাকিটা বাংলায়।"
        ),
    }]
    for img in image_data_list:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{img.get('mime_type', 'image/jpeg')};base64,{img.get('base64', '')}"},
        })

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": VISION_MODEL,
                "messages": [{"role": "user", "content": content}],
                "max_tokens": 700,
            },
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        import traceback
        print(f"[case_study_ai] analyze_report_images FAILED: {e}")
        traceback.print_exc()
        return f"(রিপোর্ট ছবি বিশ্লেষণে সমস্যা হয়েছে, স্কিপ করা হলো: {e})"
