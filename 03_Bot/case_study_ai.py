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
5. কেস অস্পষ্ট/অসম্পূর্ণ মনে হলেও, যতটুকু তথ্য আছে তা দিয়ে best-guess উত্তর দাও — প্রশ্ন করে সময় নষ্ট কোরো না।"""


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
