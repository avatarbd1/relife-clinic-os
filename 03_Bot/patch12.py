# -*- coding: utf-8 -*-
import sys

path = "case_study_ai.py"
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

old = '''    try:
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
        return f"⚠️ AI থেকে উত্তর আনতে সমস্যা হয়েছে: {e}"'''

new = '''    heavy_lessons = {8, 9}
    tokens_for_this_lesson = 2500 if lesson_number in heavy_lessons else 2000

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
            content += "\\n\\n⚠️ (উত্তরটা length limit-এ কেটে গেছে, সম্পূর্ণ নাও হতে পারে।)"
        return content
    except Exception as e:
        return f"⚠️ AI থেকে উত্তর আনতে সমস্যা হয়েছে: {e}"'''

if src.count(old) != 1:
    sys.exit("ABORT: answer_case_lesson request block not found exactly once.")
src = src.replace(old, new, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(src)
print("case_study_ai.py: patch12 applied OK")
