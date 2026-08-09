# Relife Clinic OS v2 — AI Development OS

Termux/Linux টার্মিনালে চলা একটি সিঙ্গেল-কমান্ড CLI, যা দিয়ে টাস্ক ম্যানেজমেন্ট, কোড রান, লগ ভিউ, ব্যাকআপ ও GitHub sync করা যায়।

## ইনস্টল (Termux/Linux)

```bash
cd Relife-Clinic-OS
bash install.sh
```

এরপর যেকোনো জায়গা থেকে:

```bash
relife
```

## ব্যবহার

```
relife                      -> ইন্টারঅ্যাকটিভ মেনু
relife task                 -> নতুন টাস্ক তৈরি
relife task list            -> সব টাস্ক দেখা
relife task done <id>       -> টাস্ক সম্পন্ন করা
relife task search <text>   -> টাস্ক খোঁজা

relife run <file>           -> কোড রান (.py/.sh/.js অটো ডিটেক্ট)
relife run <file> --lang python

relife logs                 -> আজকের রান লগ
relife logs run              -> সব রান লগ
relife logs error             -> এরর লগ
relife logs activity           -> অ্যাক্টিভিটি লগ
relife logs search <keyword>    -> এরর লগে খোঁজা

relife backup                -> নতুন ব্যাকআপ (ZIP)
relife backup list            -> সব ব্যাকআপ
relife backup restore <n>      -> N নম্বর ব্যাকআপ রিস্টোর
relife backup clean             -> ৭ দিনের বেশি পুরনো ব্যাকআপ মুছবে

relife sync                   -> git add + commit + push
relife sync "commit message"
relife sync status              -> git status
relife sync pull                -> git pull

relife status                 -> প্রজেক্ট ড্যাশবোর্ড (%, pending, errors)
relife doctor                  -> সিস্টেম হেলথ চেক (python/git/node আছে কিনা)
relife settings                 -> সেটিংস পরিবর্তন
```

## GitHub Sync ব্যবহারের আগে

`relife sync` কাজ করার জন্য প্রজেক্ট ফোল্ডারে একবার git init ও remote সেট করা থাকতে হবে:

```bash
git init
git remote add origin <your-repo-url>
```

## Phase Roadmap

- ✅ Phase 1 — Core CLI (menu, settings, config, sqlite db)
- ✅ Phase 2 — Task Manager (add/list/complete/search)
- ✅ Phase 3 — Code Runner (python/bash/node + logging)
- ✅ Phase 4 — GitHub Integration (status/commit/push/pull)
- ✅ Phase 5 — Backup System (zip/list/restore/clean)
- ⏳ Phase 6 — Dashboard graph, Prompt Library, Module Installer, Auto Project Generator (পরবর্তী ধাপে)

## ফোল্ডার স্ট্রাকচার

```
Relife-Clinic-OS/
├── cli/            # সব পাইথন মডিউল + মূল 'relife' এক্সিকিউটেবল
├── workspace/       # prompts, generated_code, outputs, temp, archive
├── logs/             # task_log, run_log, error_log, activity_log (JSON)
├── database/          # tasks.db (sqlite), settings.json
├── backup/             # ZIP ব্যাকআপ ফাইল
├── github/              # (future use)
├── config/               # (future use)
└── install.sh
```
