"""
text_extract.py
রোগী রেজিস্ট্রেশনের ফ্রি-টেক্সট (যেকোনো ভাষায়/ক্রমে/কমা ছাড়া লেখা) থেকে
Groq টেক্সট মডেল দিয়ে নাম/ফোন/ঠিকানা/বয়স বের করার হেল্পার।
Environment variable লাগবে: GROQ_API_KEY
"""
import os
import json
import re
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

EXTRACT_PROMPT_TMPL = """একজন ক্লিনিক স্টাফ রোগীর তথ্য এক লাইনে স্বাধীনভাবে লিখেছে (বাংলা/ইংরেজি
মিশ্রিত হতে পারে, যেকোনো ক্রমে, কমা লাগবে না)। নিচের লেখা থেকে যা যা পাওয়া যায় বের করে
শুধু এই JSON ফরম্যাটে দাও, কোনো field না পেলে null রাখো, অন্য কোনো লেখা যোগ কোরো না:

{{"full_name": null, "age": null, "phone": null, "address": null}}

স্টাফের লেখা: "{text}"
"""

def extract_patient_fields(text: str):
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY সেট করা নেই")
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_TEXT_MODEL,
        "messages": [{"role": "user", "content": EXTRACT_PROMPT_TMPL.format(text=text)}],
        "temperature": 0,
    }
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    out = resp.json()["choices"][0]["message"]["content"].strip()
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL).strip()
    out = out.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", out, flags=re.DOTALL)
    if match:
        out = match.group(0)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON parse failed, raw model output: {out[:300]}")
