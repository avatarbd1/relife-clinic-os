"""
intent_router.py
মূল মেনুতে (কোনো active conversation ছাড়া) কেউ বাটন না চেপে সরাসরি লিখলে,
Groq দিয়ে বুঝে সবচেয়ে কাছাকাছি মেনু আইটেমটা suggest করার হেল্পার।
নিরাপত্তার জন্য এটা কখনো নিজে থেকে flow শুরু করে না — শুধু সঠিক বাটন সাজেস্ট করে,
ইউজার নিজে ট্যাপ করলে তবেই আসল ConversationHandler flow শুরু হয়।
Environment variable লাগবে: GROQ_API_KEY
"""
import os
import re
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_TEXT_MODEL = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

PROMPT_TMPL = """একজন ক্লিনিক স্টাফ বটে কিছু একটা লিখেছে, কিন্তু কোনো মেনু বাটন চাপেনি। নিচের
অনুমোদিত মেনু আইটেমগুলোর মধ্যে কোনটার সাথে তার লেখা সবচেয়ে বেশি মিলে যায় বের করো:

{items}

স্টাফের লেখা: "{text}"

উপরের লিস্ট থেকে হুবহু একটা মেনু আইটেমের টেক্সট লিখো (ইমোজিসহ, হুবহু কপি করে)। কোনোটার
সাথেই স্পষ্টভাবে না মিললে শুধু NONE লিখো। অন্য কোনো লেখা/ব্যাখ্যা যোগ কোরো না।
"""

def classify_menu_intent(text: str, allowed_items: list) -> str | None:
    if not GROQ_API_KEY or not allowed_items:
        return None
    items_text = "\n".join(f"- {x}" for x in allowed_items)
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_TEXT_MODEL,
        "messages": [{"role": "user", "content": PROMPT_TMPL.format(items=items_text, text=text)}],
        "temperature": 0,
    }
    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        out = resp.json()["choices"][0]["message"]["content"].strip()
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL).strip()
        out = out.strip().strip('"').strip()
    except Exception:
        return None
    if out == "NONE" or not out:
        return None
    for item in allowed_items:
        if item.strip() == out.strip():
            return item
    return None
