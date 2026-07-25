# HANDOVER — Relife Clinic OS

## এখন অবস্থা (Last updated: manually update this)
- Bot production-এ চলছে: Termux tmux + Render দুই জায়গাতেই
- সোর্স ফোল্ডার: ~/relife-clinic-os (এটাই একমাত্র লাইভ কপি)

## এখন যা কাজ চলছে
BrainOS Step 4: BRAIN_DISPATCHER execution loop - DONE. Step 5 (Decision Engine integration) not yet started.
- (এখানে এক লাইনে লিখুন — যেমন: "staff_ai_query.py-তে OpenRouter fallback যোগ হচ্ছে")

## জানা বাগ
- Conversation state clear হয় না mid-flow /start-এ
- Phone number field-এ input validation নেই

## পরের ধাপ
- (TODO list)

## যেকোনো AI-কে কাজ শুরুর আগে
1. এই ফাইল পড়ুন
2. শুধু ~/relife-clinic-os ফোল্ডারে কাজ করুন, কোনো duplicate-এ না
3. কাজ শেষে এই ফাইলের "এখন যা কাজ চলছে" আপডেট করে দিন

## 2026-07-24 — Home folder cleanup (Termux)
- Removed duplicate/dead code copies: old `~/clinic-bot` folder, `~/archive_2026-07`, stray zips, patch scripts, diff/structure txt files.
- Before deletion, backed up `.env` and `credentials.json` from old `~/clinic-bot` to `~/clinic-bot-env-backup/`.
- Only one code folder remains: `~/relife-clinic-os`, synced with GitHub (`avatarbd1/relife-clinic-os`) and auto-deploying to Render.
- Note: `~/credentials.json` still sits directly in home root — unclear which project it belongs to, needs checking.

| BOOT-001 completed by dispatcher.py | DeepSeek-1 | 2026-07-25 15:07 | 15_BrainOS/ |

## 2026-07-25 18:57 — Step 6/10 DONE: Provider Router live test
- Extended 15_AI_Brain/Core/provider_router.py: _call_provider() now makes real HTTP calls for Groq and OpenRouter (previously simulated). Gemini call was already real but currently blocked — GEMINI_API_KEY invalid (400).
- Verified live: TASK-001 (Python Coding) routed to Groq, got real response {"result": "OK"}, status SUCCESS.
- OpenRouter verified separately via direct API test (200 OK).
- 15_AI_Brain/Control/provider_router.py confirmed unused duplicate — left in place, not deleted.
- Rotated GROQ_API_KEY and OPENROUTER_API_KEY (old ones were invalid/placeholder-like). Cleaned duplicate export lines from ~/.bashrc.
- Next: Step 7/10 - Task Router-BrainOS bridge (not started). Also: GEMINI_API_KEY still needs regeneration before Gemini can be used live.
