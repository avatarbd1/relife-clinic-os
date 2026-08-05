#!/usr/bin/env python3
"""
add_task.py — সাধারণ কথা লিখলেই AI বুঝে TASK_QUEUE-এ (BRAIN_QUEUE.md) একটা
সঠিক ফরম্যাটের টাস্ক এন্ট্রি তৈরি করে দেয়।

ব্যবহার:
  python3 add_task.py "fix my menu"
  python3 add_task.py "মেনু বাটন ক্লিক করলে সাড়া দিচ্ছে না, ঠিক করো"
"""

import sys
import os
import re
import json
from datetime import datetime

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")

# .env ফাইল থেকে GROQ_API_KEY ম্যানুয়ালি লোড করা (কোনো এক্সট্রা লাইব্রেরি ছাড়াই)
def load_env():
    env_path = os.path.join(REPO_ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

load_env()

sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain"))
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Control"))
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Core"))

from task_router_bridge import TaskRouterBridge

import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

ALLOWED_TYPES = [
    "Documentation", "Planning", "Python Coding", "Bug Fix",
    "Refactor", "Testing", "Automation", "Architecture", "Business Logic",
]
ALLOWED_PRIORITIES = ["CRITICAL", "HIGH", "NORMAL", "LOW"]

CLASSIFY_PROMPT = """তুমি একটা সফটওয়্যার প্রজেক্টের টাস্ক ক্লাসিফায়ার। ইউজার নিচে একটা
সাধারণ বাক্যে কিছু একটা ফিক্স/তৈরি করতে বলেছে। এটা বিশ্লেষণ করে শুধু নিচের JSON
ফরম্যাটে উত্তর দাও, অন্য কোনো লেখা/ব্যাখ্যা/মার্কডাউন ফেন্স ছাড়া:

{{"type": "<এই লিস্ট থেকে একটা: Documentation, Planning, Python Coding, Bug Fix, Refactor, Testing, Automation, Architecture, Business Logic>", "priority": "<CRITICAL, HIGH, NORMAL, LOW এর একটা>", "description": "<ইউজার আসলে কী চেয়েছে তার পরিষ্কার, বিস্তারিত ইংরেজি/বাংলা বর্ণনা, যাতে অন্য কোনো ডেভেলপার/AI প্রেক্ষাপট ছাড়াই বুঝতে পারে কী করতে হবে>"}}

ইউজারের কথা: "{text}"
"""


def classify(text):
    if not GROQ_API_KEY:
        print("⚠️  GROQ_API_KEY পাওয়া যায়নি (.env চেক করো) — ডিফল্ট ভ্যালু দিয়ে এগোচ্ছি।")
        return {"type": "Bug Fix", "priority": "NORMAL", "description": text}

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": CLASSIFY_PROMPT.format(text=text)}],
        "temperature": 0,
    }
    try:
        resp = requests.post(GROQ_URL, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        out = resp.json()["choices"][0]["message"]["content"].strip()
        out = re.sub(r"<think>.*?</think>", "", out, flags=re.DOTALL).strip()
        out = re.sub(r"^```(json)?|```$", "", out.strip(), flags=re.MULTILINE).strip()
        data = json.loads(out)
    except Exception as e:
        print(f"⚠️  AI ক্লাসিফিকেশন ফেইল হয়েছে ({e}) — ডিফল্ট ভ্যালু দিয়ে এগোচ্ছি।")
        return {"type": "Bug Fix", "priority": "NORMAL", "description": text}

    task_type = data.get("type", "Bug Fix")
    if task_type not in ALLOWED_TYPES:
        task_type = "Bug Fix"
    priority = str(data.get("priority", "NORMAL")).upper()
    if priority not in ALLOWED_PRIORITIES:
        priority = "NORMAL"
    description = data.get("description") or text
    return {"type": task_type, "priority": priority, "description": description}


def save_description(task_id, description, original_text):
    """description আলাদা ফাইলে সেভ করি, যাতে BRAIN_QUEUE.md-এর টেবিল
    ফরম্যাট নষ্ট না হয়, কিন্তু dispatcher পরে পুরো বর্ণনা পড়তে পারে।"""
    path = os.path.join(REPO_ROOT, "15_BrainOS", "TASK_DESCRIPTIONS.json")
    data = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[task_id] = {
        "description": description,
        "original_text": original_text,
        "created_at": datetime.now().isoformat(),
    }
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    if len(sys.argv) < 2:
        print('ব্যবহার: python3 add_task.py "তোমার কথা"')
        sys.exit(1)

    text = " ".join(sys.argv[1:])
    print(f"📝 ইনপুট: {text}")
    print("🤖 AI দিয়ে বুঝার চেষ্টা করছি...")

    result = classify(text)
    print(f"   ধরন: {result['type']}")
    print(f"   অগ্রাধিকার: {result['priority']}")
    print(f"   বর্ণনা: {result['description']}")

    bridge = TaskRouterBridge()
    task = bridge.create_and_persist_task(
        result["type"], result["description"], result["priority"]
    )

    if task.get("status") == "PROVIDER_ASSIGNED":
        save_description(task["task_id"], result["description"], text)
        print(f"\n✅ টাস্ক তৈরি হয়েছে: {task['task_id']}")
        print(f"   BRAIN_QUEUE.md-এ QUEUED অবস্থায় যোগ হয়েছে।")
        print(f"   Provider বরাদ্দ: {task.get('provider')}")
        print(f"\n   এটা রান করাতে (dispatcher চালাতে) পরে বলবে —")
        print(f"   এখনই অটো-রান হচ্ছে না।")
    else:
        print(f"\n❌ টাস্ক তৈরি ব্যর্থ হয়েছে: {task.get('error')}")


if __name__ == "__main__":
    main()
