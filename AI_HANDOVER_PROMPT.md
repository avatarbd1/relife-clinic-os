# 🤖 AI HANDOVER PROMPT — Relife Clinic OS
# এই ফাইলটি পরবর্তী AI সেশনকে পুরো প্রজেক্ট বুঝিয়ে দেওয়ার জন্য
# কপি করে যেকোনো AI-কে দিন, সব বুঝে কাজ শুরু করবে

---

## 🎯 আমি কে?
আমি ReLife Clinic OS এর Owner/Developer। এটা একটা Clinic Management System যেটা Termux (Android) + Python + Google Sheets দিয়ে চলছে।

---

## 📁 প্রজেক্ট সম্পর্কে
- **নাম:** Relife Clinic OS
- **GitHub:** https://github.com/avatarbd1/relife-clinic-os
- **Branch:** main
- **লোকেশন:** ~/relife-clinic-os
- **রানটাইম:** Python 3.14.6, Termux (Android)
- **লাইভ বট:** 03_Bot/ - Production-এ চলছে (Termux tmux + Render)

---

## 🧠 BrainOS — AI Development OS (Phase 1: 8/10 Complete)

এটা প্রজেক্টের AI brain অংশ। goal হলো পুরো clinic system-টা একটা autonomous AI-driven OS বানানো।

### Phase 1 Progress:

1. ✅ **AI_BRAIN.md Master Prompt created**
   - AI_BRAIN.md-এ master prompt v2 তৈরি হয়েছে — প্রজেক্ট context, rules, entry points সংজ্ঞায়িত করা আছে।

2. ✅ **BrainOS 5-file bootstrap (STATE/QUEUE/REGISTRY/DISPATCHER/MEMORY)**
   - 15_BrainOS/ ফোল্ডারে BRAIN_STATE.md, BRAIN_QUEUE.md, BRAIN_REGISTRY.md, BRAIN_DISPATCHER.md, BRAIN_MEMORY.md — core OS foundation তৈরি।

3. ✅ **Brain-AIOS sync (11_AIOS linked to BrainOS)**
   - 11_AIOS/ (MASTER_PROMPT, AI_CONSTITUTION, AI_REGISTRY, ONBOARDING_MESSAGE) BRAIN_DISPATCHER এবং BRAIN_REGISTRY-এর সাথে লিংক করা হয়েছে।

4. ✅ **BRAIN_DISPATCHER execution loop**
   - dispatcher.py v1.0 — 6টা control সহ: LOCK_TOKEN check, 1 task/run, no 03_Bot/ touch, whitelist paths, confirm prompt, memory logging।

5. ✅ **Decision Engine integration**
   - validate_task() ফাংশন 5টা rule enforce করে: BRAIN_QUEUE membership, TASK_QUEUE conflict check, AI_REGISTRY check, HANDOVER accessibility, completion review।

6. ✅ **Provider Router live test**
   - ProviderRouter লাইভ টেস্ট করা হয়েছে — Groq + OpenRouter কাজ করছে (real HTTP calls), Gemini invalid API key-তে block, graceful mock fallback confirmed।

7. ✅ **Task Router-BrainOS Bridge**
   - task_router_bridge.py TASK_ROUTER.py extend করে — task গুলো auto-persist হয় BRAIN_QUEUE.md, BRAIN_STATE.md, HANDOVER.md, BRAIN_MEMORY.md-এ।

8. ✅ **Provider Router + AI Registry Integration**
   - registry_provider_bridge.py ProviderRouter-কে AI_REGISTRY.md-এর সাথে কানেক্ট করে — registry-aware routing, provider health reports, actual vs registry status auto-sync।

9. ⏳ **Self-Healing Monitor** (PENDING)
   - করতে হবে: 15_AI_Brain/Monitor/self_healing.py তৈরি — broken references, missing files, API key issues, provider failures auto-detect করে health report জেনারেট করবে।

10. ⏳ **Full Autonomous Loop Test** (PENDING)
    - করতে হবে: 3টা test task সম্পূর্ণ flow-এ চালাতে হবে (Task → Route → Execute → Log → Update) কোনো human intervention ছাড়া, সব control ভেরিফাই করতে হবে, তারপর Phase 1 COMPLETE মার্ক করতে হবে।

---

## ⚠️ গুরুত্বপূর্ণ নিয়ম (Rules for AI)
- **03_Bot/ (live bot code) কখনো টাচ করবে না** কোনো explicit permission ছাড়া — এটা production-এ চলছে।
- সব নতুন change করার আগে BRAIN_QUEUE.md এবং TASK_QUEUE.md চেক করবে conflict আছে কিনা।
- কাজ শেষে অবশ্যই BRAIN_STATE.md এবং BRAIN_MEMORY.md আপডেট করবে (handover continuity-র জন্য)।
- Owner-এর ভাষা মূলত Bangla/English মিক্স, ইনফরমাল — দ্রুত decision-oriented রেসপন্স প্রেফার করে, বেশি clarifying question না করে।

---

## ➡️ পরবর্তী ধাপ (Immediate Next Steps)
Phase 1 শেষ করতে বাকি ২টা কাজ:
1. Self-Healing Monitor বানানো (15_AI_Brain/Monitor/self_healing.py)
2. Full Autonomous Loop Test চালানো এবং Phase 1 COMPLETE মার্ক করা

