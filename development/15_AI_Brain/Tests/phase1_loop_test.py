#!/usr/bin/env python3
"""
phase1_loop_test.py — BrainOS Phase 1, Item 10: Full Autonomous Loop Test
Relife Clinic OS
"""

import os
import sys
from datetime import datetime

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
os.chdir(REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "development/15_AI_Brain"))
sys.path.insert(0, os.path.join(REPO_ROOT, "development/15_AI_Brain", "Control"))

from task_router_bridge import TaskRouterBridge  # noqa: E402

TEST_TASKS = [
    ("Documentation", "Phase1 LoopTest Task A - doc stub", "NORMAL"),
    ("Testing", "Phase1 LoopTest Task B - test stub", "HIGH"),
    ("Automation", "Phase1 LoopTest Task C - automation stub", "CRITICAL"),
]

FILES_TO_WATCH = [
    "development/15_BrainOS/BRAIN_QUEUE.md",
    "development/15_BrainOS/BRAIN_STATE.md",
    "development/12_Handover/HANDOVER.md",
    "development/15_BrainOS/BRAIN_MEMORY.md",
]


def snapshot_files():
    snap = {}
    for path in FILES_TO_WATCH:
        if os.path.exists(path):
            snap[path] = os.path.getmtime(path)
        else:
            snap[path] = None
    return snap


def main():
    print("=" * 60)
    print("PHASE 1 — ITEM 10: FULL AUTONOMOUS LOOP TEST")
    print("=" * 60)

    bridge = TaskRouterBridge()
    results = []

    before = snapshot_files()

    for i, (task_type, description, priority) in enumerate(TEST_TASKS, start=1):
        print(f"\n--- Test Task {i}/3: {description} ---")
        try:
            task = bridge.create_and_persist_task(task_type, description, priority)
            passed = task.get("status") == "PROVIDER_ASSIGNED"
            results.append({
                "task_num": i,
                "description": description,
                "task_id": task.get("task_id"),
                "provider": task.get("provider"),
                "status": task.get("status"),
                "passed": passed,
            })
            if passed:
                print(f"   ✅ Routed → provider: {task.get('provider')}, task_id: {task.get('task_id')}")
            else:
                print(f"   ❌ FAILED: {task}")
        except Exception as e:
            results.append({
                "task_num": i,
                "description": description,
                "task_id": None,
                "provider": None,
                "status": f"EXCEPTION: {e}",
                "passed": False,
            })
            print(f"   ❌ EXCEPTION: {e}")

    after = snapshot_files()

    print("\n--- File Update Check ---")
    file_check_passed = True
    for path in FILES_TO_WATCH:
        changed = before[path] != after[path]
        mark = "✅" if changed else "❌"
        if not changed:
            file_check_passed = False
        print(f"   {mark} {path} — {'updated' if changed else 'NOT updated'}")

    all_tasks_passed = all(r["passed"] for r in results)
    overall_pass = all_tasks_passed and file_check_passed

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for r in results:
        mark = "✅" if r["passed"] else "❌"
        print(f"  {mark} Task {r['task_num']}: {r['description']} → {r['status']}")
    print(f"\n  File updates: {'✅ all files touched' if file_check_passed else '❌ some files NOT touched'}")
    print(f"\n  OVERALL: {'🟢 PASS — Phase 1 Item 10 COMPLETE' if overall_pass else '🟡 FAIL — needs review'}")

    report_path = "development/15_AI_Brain/Tests/PHASE1_LOOP_TEST_REPORT.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Phase 1 Item 10 — Full Autonomous Loop Test Report\n")
        f.write(f"_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n\n")
        for r in results:
            mark = "✅" if r["passed"] else "❌"
            f.write(f"- {mark} Task {r['task_num']}: {r['description']} → `{r['status']}` (provider: {r['provider']}, task_id: {r['task_id']})\n")
        f.write(f"\n**File updates:** {'✅ all touched' if file_check_passed else '❌ incomplete'}\n")
        f.write(f"\n**Overall:** {'🟢 PASS' if overall_pass else '🟡 FAIL'}\n")

    print(f"\n[phase1_loop_test] Report written to: {report_path}")
    sys.exit(0 if overall_pass else 1)


if __name__ == "__main__":
    main()
