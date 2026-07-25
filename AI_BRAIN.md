# 🧠 AI_BRAIN.md — Single Source of Truth
# Project: relife-clinic-os
# Born: 2026-07-24

---

## 🤖 MASTER PROMPT v2

তুই এই রিপোজিটরির AI। তোর কর্তৃত্ব:
1. BRAIN READ: প্রথমেই AI_BRAIN.md পড়বি
2. TASK SPLIT: কাজ ১০ ধাপে ভাগ করবি
3. AUTO LOG: প্রতি ধাপে append-only লগ করবি
4. SINGLE COMMAND: প্রয়োজনে ১টি Termux command চাইবি
5. GIT PUSH: শেষ ধাপে git push করবি
6. NO REPEAT: একই তথ্য দ্বিতীয়বার চাইবি না
7. NO DESTROY: approval ছাড়া delete করবি না

---

## 📋 HANDOFF PROTOCOL

Session limit শেষে:
- Brain-এ ধাপ নম্বর লগ কর
- WIP branch-এ push কর
- পরবর্তী AI-কে বল: "ধাপ X থেকে শুরু করো"

---

## 🔧 AUTO-HEALING

Brain corrupt হলে:
- git log AI_BRAIN.md দেখ
- Last good commit থেকে restore কর
- মানুষকে alert কর

---

## 🔒 LOCK TOKEN

একই সময়ে শুধু ১টা AI active
LOCK_TOKEN থাকলে অপেক্ষা কর

---

## 📟 ৩টা COMMAND

১. git clone (প্রথম বার)
২. AI-র ১টা command (প্রতি ধাপে)
৩. git push (শেষ ধাপে)

---

## 🇧🇩 BANGLA-FIRST

Output বাংলায়, code comment ইংরেজিতে

---

## 📊 PROGRESS LOG

[2026-07-24] AI_BRAIN তৈরি
Status: DONE
Next: Brain Automation ধাপ ২/১০
Lock: FREE

---

[2026-07-24] [AI: Claude] Phase 2: Dashboard Layer completed
Status: DONE
Milestone: 009 ✅
Next: Brain-AIOS sync
Session: Active

[2026-07-25] [AI: DeepSeek] BrainOS 5-file bootstrap completed
Status: DONE
Milestone: Phase 1 Step 2 ✅
Next: Brain-AIOS sync (Step 3/10)
Session: Active

[2026-07-25] [AI: DeepSeek] Brain-AIOS sync completed
Status: DONE
Milestone: Phase 1 Step 3 ✅
Next: BRAIN_DISPATCHER execution loop (Step 4/10)
Session: Active

[2026-07-25] [AI: DeepSeek] BRAIN_DISPATCHER execution loop (dispatcher.py) completed
Status: DONE
Milestone: Phase 1 Step 4 ✅
Next: Decision Engine integration (Step 5/10) - NOT STARTED
Session: Paused

[2026-07-25] [AI: DeepSeek] Decision Engine integration completed
Status: DONE
Milestone: Phase 1 Step 5 ✅
Next: Provider Router live test (Step 6/10) - NOT STARTED
Session: Paused

[2026-07-25] [AI: DeepSeek] Decision Engine integration complete (dispatcher.py validate_task 5 rules) + Gemini REST API wired. Live test: Gemini key invalid (400), graceful fallback to OpenRouter mock works.
Status: Step 5 DONE. Step 6 partially blocked - needs valid Gemini API key.
