# 🧠 BrainOS Phase 2 Roadmap — Real Autonomous Execution
_Relife Clinic OS_

Phase 1 বানিয়েছে **কাঠামো** (task routing, state files, health monitor, loop test)।
Phase 2-এর লক্ষ্য: এই কাঠামোকে দিয়ে **সত্যিকারের কাজ** করানো — নিজে থেকে, নিরাপদে, ট্র্যাক করা অবস্থায়।

**নিয়ম (Phase 1-এর মতোই বহাল থাকবে):**
- `03_Bot/` কখনো explicit owner-permission ছাড়া touch হবে না
- প্রতিটা item-এর একটা "marker" আছে (নিচে) — marker file/folder থাকলে auto-tracker সেটাকে ✅ ধরবে
- Auto-tracker কোনো কাজ নিজে করে না, শুধু progress detect করে রিপোর্ট বানায়

---

## Task List

### 1. Task Executor
**কী করতে হবে:** Provider route করার পরে, provider-কে দিয়ে আসল কাজ (কোড/ডকুমেন্টেশন লেখা) করানো এবং সেই output ফাইলে সেভ করা — এখন পর্যন্ত শুধু "কোন provider assigned হলো" পর্যন্ত টেস্ট হয়েছে, provider আসল output দিচ্ছে কিনা সেটা না।
**Marker:** `15_AI_Brain/Core/task_executor.py`
**Status:** ⏳ Pending

### 2. Dry-Run + Confirm Gate
**কী করতে হবে:** Provider-এর output সরাসরি ফাইলে write না করে, প্রথমে একটা "proposed change" হিসেবে দেখানো, owner/AI confirm করলে তবেই apply। বিশেষ করে `03_Bot/`-এর কাছাকাছি যেকোনো কিছুর জন্য বাধ্যতামূলক।
**Marker:** `15_AI_Brain/Control/confirm_gate.py`
**Status:** ⏳ Pending

### 3. Output Validator
**কী করতে হবে:** Provider-এর output apply করার আগে validate করা — Python হলে `py_compile`, JSON হলে `json.loads`, Markdown হলে basic structure check।
**Marker:** `15_AI_Brain/Core/output_validator.py`
**Status:** ⏳ Pending

### 4. Task Result Logger
**কী করতে হবে:** প্রতিটা task-এর input, provider, output, validation result, timestamp — permanent history ফাইলে জমা রাখা (BRAIN_MEMORY.md এর থেকে বেশি detailed, structured JSON/log)।
**Marker:** `15_AI_Brain/Logs/TASK_RESULTS.jsonl`
**Status:** ⏳ Pending

### 5. Scheduler (Self-Healing + Loop Test অটো-রান)
**কী করতে হবে:** Self-Healing Monitor আর queue-processing নিজে থেকে নিয়মিত (যেমন প্রতিদিন / প্রতি ৬ ঘণ্টা) চলবে — Termux-এ cron বা Termux:Boot বা একটা simple background loop দিয়ে।
**Marker:** `15_AI_Brain/Control/scheduler.py`
**Status:** ⏳ Pending

### 6. Failure Alerting
**কী করতে হবে:** কোনো task fail করলে, provider down থাকলে, বা health check-এ critical issue পেলে — owner-কে notify করা (Telegram বট দিয়েই, যেহেতু already আছে)।
**Marker:** `15_AI_Brain/Control/alert_notifier.py`
**Status:** ⏳ Pending

### 7. Concurrency Lock
**কী করতে হবে:** একসাথে দুইটা AI session/process যেন একই task বা একই ফাইলে কাজ না করে — একটা lock file/mechanism (dispatcher.py-এর LOCK_TOKEN ধারণাটা পুরো system-এ extend করা)।
**Marker:** `15_AI_Brain/Control/concurrency_lock.py`
**Status:** ⏳ Pending

### 8. Progress Dashboard
**কী করতে হবে:** Phase 1 + Phase 2-এর সব কিছুর একটা human-readable একনজর status view — health, queue, recent task results, সব এক জায়গায়।
**Marker:** `15_AI_Brain/Monitor/DASHBOARD.md` (auto-generated, hardcoded লেখা না — script দিয়ে বানাতে হবে)
**Status:** ⏳ Pending

---

## Auto-Tracking

এই roadmap-এর progress ম্যানুয়ালি মার্ক করার দরকার নেই। রান করুন:
এটা repo স্ক্যান করে প্রতিটা item-এর marker file/folder আছে কিনা দেখে, এবং
`15_AI_Brain/Monitor/PHASE2_PROGRESS.md`-এ আপডেটেড status লিখে দেয়।
যত marker file তৈরি হবে (অর্থাৎ যত কাজ আসলেই হবে), তত item auto-এ ✅ হয়ে যাবে —
কারো কিছু নিজে থেকে চেকলিস্ট টিক দিতে হবে না।
