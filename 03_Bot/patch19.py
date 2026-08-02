# -*- coding: utf-8 -*-
import sys

path = "case_study_ai.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

replacements = []

# ১) CURRICULUM_CONTEXT rule 4 — উত্তরের ভাষা
old1 = '4. উত্তর অবশ্যই বাংলায়, সংক্ষিপ্ত, Telegram মেসেজ আকারে দাও (heavy markdown ছাড়া, সাধারণ বুলেট পয়েন্ট ঠিক আছে)।'
new1 = '4. Answer must be in English, concise, in Telegram message format (no heavy markdown, simple bullet points are fine).'
replacements.append((old1, new1))

# ২) CURRICULUM_CONTEXT rule 6 — ভাষার নিয়ম
old2 = '6. ভাষা: সাধারণ ব্যাখ্যা বাংলায় লিখবে, কিন্তু মেডিক্যাল Terminology (Test নাম, Condition নাম, Muscle/Joint/Nerve নাম) ইংরেজিতেই রাখবে, বাংলা অনুবাদ কোরো না।"""'
new2 = '6. Language: Write the entire answer in English, including all medical terminology (test names, condition names, muscle/joint/nerve names)."""'
replacements.append((old2, new2))

# ৩) LESSON_SYSTEM_PROMPT — ভাষার নিয়ম
old3 = '- ভাষার নিয়ম: রোগীর সাথে সরাসরি সম্পর্কিত অংশ (History taking প্রশ্ন, Chief Complaint, রোগীকে কী বলবে) স্বাভাবিক সহজ বাংলায়। কিন্তু সব মেডিক্যাল Terminology, Test-নাম, Condition-নাম, Muscle/Joint/Nerve-নাম ইংরেজিতেই রাখো, বাংলা অনুবাদ কোরো না। বাকি ব্যাখ্যা বাংলায়।'
new3 = '- Language rule: Write the entire lesson in English — including patient-facing parts (history taking questions, chief complaint, what to tell the patient) and all medical terminology, test names, condition names, muscle/joint/nerve names.'
replacements.append((old3, new3))

# ৪) Vision prompt — শেষ ভাষার লাইন
old4 = '''            "মেডিক্যাল Terminology ইংরেজিতে রাখো, বাকিটা বাংলায়।"
        ),
    }]'''
new4 = '''            "Write your entire response in English, including medical terminology."
        ),
    }]'''
replacements.append((old4, new4))

for i, (old, new) in enumerate(replacements, 1):
    count = src.count(old)
    if count != 1:
        sys.exit(f"ABORT: replacement #{i} matched {count} times (expected 1). Check exact text.")
    src = src.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("case_study_ai.py: patch19 applied OK — all 4 AI output language rules switched to English")
