"""
ai_helper.py
বটের বিভিন্ন ফ্লোতে এক লাইনের বাক্য থেকে স্ট্রাকচার্ড ডেটা বের করার জন্য Groq-ভিত্তিক হেল্পার।
Environment variable লাগবে: GROQ_API_KEY
"""
import os
import json
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL_NAME = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _call_groq(prompt: str) -> str:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY সেট করা নেই")
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL_NAME, "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def parse_register_entry(text: str) -> dict | None:
    prompt = f"""নিচের বাক্যটা একটা ক্লিনিকের রোগীর পেমেন্ট এন্ট্রি হতে পারে:

"{text}"

যদি এই বাক্যে কোনো টাকার পরিমাণ উল্লেখ থাকে, তাহলে শুধু এই JSON ফরম্যাটে উত্তর দাও, অন্য কিছু লিখবে না:
{{"name": "রোগীর নাম", "amount": সংখ্যা, "sessions": 1 অথবা 2}}

sessions উল্লেখ না থাকলে 1 ধরবে। যদি বাক্যে কোনো টাকার অংক না থাকে (এটা শুধু নাম/ফোন/আইডি
খোঁজার একটা সার্চ), তাহলে শুধু লিখো: NONE
"""
    try:
        raw = _call_groq(prompt)
    except Exception:
        return None
    raw = raw.strip()
    if raw.upper().startswith("NONE"):
        return None
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        name = str(data.get("name", "")).strip()
        if not name:
            return None
        return {
            "name": name,
            "amount": float(data.get("amount", 0) or 0),
            "sessions": int(data.get("sessions", 1) or 1),
        }
    except Exception:
        return None
