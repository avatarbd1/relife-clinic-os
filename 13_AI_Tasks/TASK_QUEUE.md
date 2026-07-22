# TASK QUEUE — relife-clinic-os

নিয়ম:
- কোনো কাজ শুরু করার আগে AI অবশ্যই এখানে চেক করবে সেটা অন্য কোনো
  AI ধরে আছে কিনা (In-Progress)।
- কাজ শুরু করলে নিজের ID ও তারিখ দিয়ে status "In-Progress" করবে।
- কাজ শেষ হলে status "Done" করবে এবং HANDOVER.md-এ এন্ট্রি লিখবে।
- একই সময়ে একই ফাইল/মডিউলে দুইজন AI কাজ করবে না।

---

## Pending (এখনো শুরু হয়নি)

| কাজ | মডিউল/ফাইল | অগ্রাধিকার |
|-----|------------|------------|
| Salary System (design ready, code বাকি) | sheets.py + bot.py + roles.py | High |

## In-Progress

| কাজ | AI ID | শুরুর তারিখ | মডিউল/ফাইল |
|-----|-------|-------------|------------|
| Patch 3: Back button (booking + treatment machine) | Claude-2 | 2026-07-23 | 03_Bot/bot.py |

## Done

| কাজ | AI ID | তারিখ | মডিউল/ফাইল |
|-----|-------|-------|------------|
| Patient Action Panel auto-attach (Patch 1) | Claude-1 | (আগের তারিখ) | 03_Bot/bot.py |
| Search-result keyboard merge + cancel buttons (Patch 2) | Claude-1 | (আগের তারিখ) | 03_Bot/bot.py |
| AI Workspace setup (Constitution/Master Prompt/Registry/Handover) | Claude-1 | 2026-07-23 | 11_AIOS, 12_Handover |

