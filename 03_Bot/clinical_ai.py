"""
clinical_ai.py — AI Clinical Assistant, Relife Physiotherapy Clinical Manual-এর
উপর ভিত্তি করে। staff_ai_query.py-এর মতোই দুই-ধাপের প্যাটার্ন: Groq দিয়ে relevant
condition বাছাই, তারপর OpenRouter দিয়ে বাংলায় guidance তৈরি।
"""
import os
import json
import requests

CONDITIONS_DIR = os.path.join(os.path.dirname(__file__), "clinical_conditions")
INDEX_PATH = os.path.join(CONDITIONS_DIR, "index.json")
CORE_MODULES_PATH = os.path.join(CONDITIONS_DIR, "core_modules.md")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL_NAME = "llama-3.3-70b-versatile"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL_NAME = "openai/gpt-4o-mini"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ক্লিনিকে বাস্তবে যা যা আছে — নতুন কিছু কেনা হলে শুধু এই লিস্টটা আপডেট করলেই হবে,
# বাকি কোড অপরিবর্তিত থাকবে। AI শুধু এই লিস্ট থেকেই modality/tool recommend করবে।
CLINIC_EQUIPMENT = [
    "TENS", "IFT", "Ultrasound", "SWD (Short Wave Diathermy)", "Shockwave Therapy", "EMS",
    "Dry Needling", "Electroacupuncture",
    "Hot Pack", "Cold Pack/Ice", "Wax Bath",
    "ISTM (Myofascial Release tool)", "Mulligan Belt", "Cupping",
    "Theraband", "Basketball (functional/proprioception training)",
    "Manual Therapy (hands-on techniques, no equipment needed)",
    "Exercise Therapy (bodyweight/free exercise, no equipment needed)",
]


def _call_groq(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": GROQ_MODEL_NAME, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.2, "max_tokens": 50}
    resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _call_openrouter(prompt: str) -> str:
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": OPENROUTER_MODEL_NAME, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0.3, "max_tokens": 900}
    resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=45)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def _load_index():
    with open(INDEX_PATH, encoding="utf-8") as f:
        return json.load(f)


def _load_condition_text(filename: str) -> str:
    path = os.path.join(CONDITIONS_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return f.read()


def _load_core_modules_text() -> str:
    """Manual Therapy / Exercise / Contraindications modules — always included
    alongside the matched condition, since these hold the actual technique-level
    detail (grip, dosage, Mulligan/MET protocols etc.) that condition sections only
    reference by name rather than repeat in full."""
    try:
        with open(CORE_MODULES_PATH, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _pick_relevant_conditions(case_text: str, top_n: int = 2) -> list:
    index = _load_index()
    listing = "\n".join(f"{c['id']}: {c['title']}" for c in index)
    prompt = (
        "তুমি একজন physiotherapy triage assistant। নিচে ৩০টা condition-এর তালিকা "
        "এবং একজন রোগীর presentation দেওয়া আছে। তালিকা থেকে সবচেয়ে relevant "
        f"{top_n}টা (বা কম, স্পষ্ট একটা মিললে) condition-এর ID বেছে দাও।\n\n"
        f"Condition তালিকা:\n{listing}\n\n"
        f"রোগীর presentation:\n{case_text}\n\n"
        "শুধু comma দিয়ে আলাদা করা ID লিখো, অন্য কিছু না। উদাহরণ: B2,B3"
    )
    raw = _call_groq(prompt)
    picked_ids = [x.strip().upper() for x in raw.split(",") if x.strip()]
    id_to_entry = {c["id"]: c for c in index}
    matched = [id_to_entry[i] for i in picked_ids if i in id_to_entry]
    return matched[:top_n]


def _generate_guidance(case_text: str, matched_conditions: list) -> str:
    if not matched_conditions:
        return ("দুঃখিত, এই presentation-এর সাথে manual-এর কোনো নির্দিষ্ট condition স্পষ্টভাবে "
                "মিলছে না। আরও details দিয়ে আবার চেষ্টা করুন, অথবা সিনিয়র থেরাপিস্ট/ডাক্তারের "
                "সাথে পরামর্শ করুন।")
    equipment_line = "ক্লিনিকে বাস্তবে উপলব্ধ যন্ত্রপাতি/টুলস: " + ", ".join(CLINIC_EQUIPMENT) + (
        "। শুধু এই তালিকা থেকেই modality/tool recommend করো — manual-এ অন্য কিছুর কথা "
        "থাকলেও তা যদি এই তালিকায় না থাকে, সেটা উল্লেখ না করে বরং তালিকায় থাকা কাছাকাছি "
        "বিকল্প বা হাতে-করা (manual/exercise-based, equipment ছাড়া) পদ্ধতি suggest করো।"
    )
    context_blocks = [equipment_line]
    core_text = _load_core_modules_text()
    if core_text:
        context_blocks.append(core_text)
    for c in matched_conditions:
        text = _load_condition_text(c["file"])
        context_blocks.append(f"### {c['id']} — {c['title']}\n{text}")
    context = "\n\n---\n\n".join(context_blocks)
    prompt = (
        "তুমি Relife Physiotherapy Center-এর একজন সহকারী ক্লিনিক্যাল অ্যাসিস্ট্যান্ট। "
        "নিচে manual থেকে নেওয়া প্রাসঙ্গিক condition-এর তথ্য এবং একজন থেরাপিস্টের patient "
        "presentation দেওয়া আছে। শুধু এই তথ্যের ভিত্তিতে, বাংলায়, সংক্ষিপ্ত ও practical "
        "guidance দাও — Assessment-এ কী দেখতে হবে, কোনো Red Flag থাকলে সবার আগে highlight "
        "করো, phase-wise Exercise/Treatment approach, এবং Progression Criteria। তথ্যে "
        "না থাকা কিছু অনুমান করে বলো না।\n\n"
        f"Manual তথ্য:\n{context}\n\n"
        f"থেরাপিস্টের presentation:\n{case_text}\n\n"
        "উত্তর দাও একজন সিনিয়র কলিগের মতো, স্পষ্ট ও to-the-point ভাষায়, Telegram মেসেজ "
        "ফরম্যাটে (heavy markdown ছাড়া)।"
    )
    return _call_openrouter(prompt)


def get_clinical_guidance(case_text: str):
    if not GROQ_API_KEY or not OPENROUTER_API_KEY:
        return ("⚠️ AI Clinical Assistant এখনো সেটআপ হয়নি (GROQ_API_KEY বা OPENROUTER_API_KEY নেই)।", "")
    try:
        matched = _pick_relevant_conditions(case_text)
        answer = _generate_guidance(case_text, matched)
        matched_summary = (
            ", ".join(f"{c['id']} ({c['title']})" for c in matched)
            if matched else "কোনো নির্দিষ্ট condition মেলেনি"
        )
        return answer, matched_summary
    except Exception as e:
        return f"⚠️ AI থেকে উত্তর আনতে সমস্যা হয়েছে: {e}", ""
