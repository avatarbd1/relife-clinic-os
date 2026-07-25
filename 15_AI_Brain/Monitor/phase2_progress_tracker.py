#!/usr/bin/env python3
"""
phase2_progress_tracker.py — BrainOS Phase 2 Auto Progress Tracker
Relife Clinic OS
"""

import os
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CANDIDATE_ROOTS = [Path.cwd(), SCRIPT_DIR.parent.parent]
PROJECT_ROOT = None
for candidate in CANDIDATE_ROOTS:
    if (candidate / "03_Bot").exists() or (candidate / "AI_BRAIN.md").exists():
        PROJECT_ROOT = candidate
        break
if PROJECT_ROOT is None:
    PROJECT_ROOT = Path.cwd()

REPORT_PATH = PROJECT_ROOT / "15_AI_Brain" / "Monitor" / "PHASE2_PROGRESS.md"

PHASE2_ITEMS = [
    ("1. Task Executor", "15_AI_Brain/Core/task_executor.py"),
    ("2. Dry-Run + Confirm Gate", "15_AI_Brain/Control/confirm_gate.py"),
    ("3. Output Validator", "15_AI_Brain/Core/output_validator.py"),
    ("4. Task Result Logger", "15_AI_Brain/Logs/TASK_RESULTS.jsonl"),
    ("5. Scheduler", "15_AI_Brain/Control/scheduler.py"),
    ("6. Failure Alerting", "15_AI_Brain/Control/alert_notifier.py"),
    ("7. Concurrency Lock", "15_AI_Brain/Control/concurrency_lock.py"),
    ("8. Progress Dashboard", "15_AI_Brain/Monitor/DASHBOARD.md"),
]


def main():
    results = []
    for name, marker in PHASE2_ITEMS:
        full_path = PROJECT_ROOT / marker
        done = full_path.exists()
        results.append((name, marker, done))

    done_count = sum(1 for _, _, d in results if d)
    total = len(results)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append("# 📊 BrainOS Phase 2 — Auto Progress Report")
    lines.append(f"_Generated: {now}_")
    lines.append("")
    lines.append(f"**Progress: {done_count}/{total} items complete**")
    lines.append("")

    for name, marker, done in results:
        mark = "✅" if done else "⏳"
        lines.append(f"- {mark} **{name}** — `{marker}`")

    lines.append("")
    if done_count == total:
        lines.append("🟢 **Phase 2 COMPLETE!**")
    else:
        remaining = [name for name, _, done in results if not done]
        lines.append(f"🟡 বাকি {total - done_count} টা: " + ", ".join(remaining))

    lines.append("")
    lines.append("_এই রিপোর্ট auto-generated। ম্যানুয়ালি এডিট করবেন না — মার্কার ফাইল তৈরি হলেই এটা আপডেট হয়ে যাবে পরের রানে।_")

    report_text = "\n".join(lines)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_text, encoding="utf-8")

    print(report_text)
    print(f"\n[phase2_progress_tracker] Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
