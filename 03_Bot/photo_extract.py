"""
photo_extract.py
রোগী রেজিস্ট্রেশনের ছবি (x-ray report ইত্যাদি) থেকে
Groq vision model দিয়ে ডিটেইলস বের করার হেল্পার।
Environment variable লাগবে: GROQ_API_KEY
"""
import os
import json
import base64
import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_VISION_MODEL = "qwen/qwen3.6-27b"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

EXTRACT_PROMPT = """এই ছবিটা একটা ক্লিনিক রোগীর report/document।
এখান থেকে যা যা পাওয়া যায় বের করে শুধু এই JSON ফরম্যাটে দাও,
কোনো field না পেলে null রাখো, অন্য কোনো লেখা যোগ কোরো না:

{"full_name": null, "age": null, "phone": null, "address": null, "gender": null}
"""

def extract_from_photo(image_bytes: bytes) -> dict | None:
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY সেট করা নেই")

    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACT_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{b64_image}"
                        },
                    },
                ],
            }
        ],
        "temperature": 0,
    }
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"].strip()
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise RuntimeError(f"JSON parse failed, raw model output: {text[:300]}")
