# -*- coding: utf-8 -*-
import sys

path = "case_study_ai.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

# ১) মডেল ফ্রি করা
old_model = 'MODEL = "openai/gpt-4o-mini"'
new_model = 'MODEL = "meta-llama/llama-3.3-70b-instruct:free"'
if src.count(old_model) != 1:
    sys.exit("ABORT: MODEL line not found exactly once.")
src = src.replace(old_model, new_model, 1)

# ২) requests ইম্পোর্টের পরে time ইম্পোর্ট যোগ করা (retry-তে লাগবে)
if "\nimport time\n" not in src and not src.startswith("import time\n"):
    src = src.replace("import requests\n", "import requests\nimport time\n", 1)

# ৩) answer_case_lesson-এর try/except ব্লক replace করে retry যোগ করা
old_block = '''    try:
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
            content += "\\n\\n⚠️ (উত্তরটা length limit-এ কেটে গেছে, সম্পূর্ণ নাও হতে পারে।)"
        return content
    except Exception as e:
        return f"⚠️ AI থেকে উত্তর আনতে সমস্যা হয়েছে: {e}"'''

new_block = '''    # ফ্রি মডেল ব্যবহার করলে মাঝে মাঝে rate-limit (429) হিট হতে পারে —
    # তাই একবার ব্যর্থ হলে ১৫ সেকেন্ড অপেক্ষা করে সর্বোচ্চ ২ বার retry করা হচ্ছে।
    last_error = None
    for attempt in range(3):
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
            if resp.status_code == 429 and attempt < 2:
                time.sleep(15)
                continue
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"]["content"].strip()
            if choice.get("finish_reason") == "length":
                content += "\\n\\n⚠️ (উত্তরটা length limit-এ কেটে গেছে, সম্পূর্ণ নাও হতে পারে।)"
            return content
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(5)
                continue
    return f"⚠️ AI থেকে উত্তর আনতে সমস্যা হয়েছে: {last_error}"'''

if src.count(old_block) != 1:
    sys.exit("ABORT: answer_case_lesson request block not found exactly once.")
src = src.replace(old_block, new_block, 1)

# ৪) MCQ refusal বন্ধ করার জন্য প্রম্পটে স্পষ্ট নির্দেশ যোগ
old_rule = '- রোগীর আর্থিক অবস্থা বিবেচনা করো। যত কম Test করে নিরাপদ Diagnosis করা যায় সেই নীতি অনুসরণ করো।'
new_rule = '''- রোগীর আর্থিক অবস্থা বিবেচনা করো। যত কম Test করে নিরাপদ Diagnosis করা যায় সেই নীতি অনুসরণ করো।
- MCQ/Viva Lesson চাওয়া হলে কখনো "আমি সক্ষম নই" জাতীয় কথা বলে refuse কোরো না — এটা তোমার নিয়মিত, সাধারণ শিক্ষাদান কাজের অংশ। রোগীর কেস থেকে প্রাসঙ্গিক প্রশ্ন-উত্তর/MCQ (option A/B/C/D সহ, সঠিক উত্তর ও ছোট ব্যাখ্যাসহ) তৈরি করাই তোমার দায়িত্ব।'''
if src.count(old_rule) != 1:
    sys.exit("ABORT: MCQ refusal-fix anchor rule not found exactly once.")
src = src.replace(old_rule, new_rule, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("case_study_ai.py: patch16 applied OK (free model + retry logic + MCQ refusal fix)")
