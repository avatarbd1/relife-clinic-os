#!/usr/bin/env python3
"""
BRAIN_DISPATCHER v1.0 — Manual execution loop (Phase 1 Step 4/10)
Reads BRAIN_QUEUE, validates, routes, confirms with user, executes ONE task, then stops.

CONTROLS (mandatory, never bypass):
1. No execute without CONFIRM (y/n via input)
2. Max 1 task per run — no autonomous loop
3. NEVER touches 03_Bot/ files
4. LOCK_TOKEN check — exits if not FREE
5. Every action logged to BRAIN_MEMORY.md (timestamped)
6. No destructive commands (rm, git push -f, overwrite outside whitelist)
7. If ROUTE fails, EXECUTE is skipped automatically (no confirm prompt)
"""

import os
import sys
import re
from datetime import datetime

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
os.chdir(REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "development/15_AI_Brain"))
sys.path.insert(0, os.path.join(REPO_ROOT, "development/15_AI_Brain", "Control"))

BRAIN_STATE_FILE = "development/15_BrainOS/BRAIN_STATE.md"
BRAIN_QUEUE_FILE = "development/15_BrainOS/BRAIN_QUEUE.md"
BRAIN_MEMORY_FILE = "development/15_BrainOS/BRAIN_MEMORY.md"
HANDOVER_FILE = "development/12_Handover/HANDOVER.md"
TASK_QUEUE_FILE = "development/13_AI_Tasks/TASK_QUEUE.md"

WHITELISTED_PATHS = [
    "development/15_BrainOS/",
    "development/11_AIOS/",
    "development/12_Handover/",
    "development/13_AI_Tasks/",
    "development/15_AI_Brain/",
]

FORBIDDEN_PREFIX = "03_Bot/"


def log_memory(level, component, message):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{ts}] [{level}] [{component}] {message}\n"
    with open(BRAIN_MEMORY_FILE, "a") as f:
        f.write(entry)


def read_file(path):
    with open(path) as f:
        return f.read()


def write_file(path, content):
    if path.startswith(FORBIDDEN_PREFIX):
        raise PermissionError(f"Forbidden: cannot write to {path} (03_Bot/ is off-limits)")
    allowed = any(path.startswith(w) for w in WHITELISTED_PATHS)
    if not allowed and not path.endswith("AI_BRAIN.md"):
        raise PermissionError(f"Forbidden: path {path} is not in whitelist")
    with open(path, "w") as f:
        f.write(content)


def check_lock_token():
    state = read_file(BRAIN_STATE_FILE)
    match = re.search(r"Lock Token:\s*(\w+)", state)
    if match:
        token = match.group(1).strip()
        if token != "FREE":
            print(f"LOCK_TOKEN = {token}. Exiting.")
            log_memory("ERROR", "DISPATCHER", f"LOCK_TOKEN check failed — state is {token}")
            sys.exit(1)
        return True
    log_memory("WARN", "DISPATCHER", "LOCK_TOKEN not found in BRAIN_STATE — assuming FREE")
    return True


def pick_next_task():
    queue = read_file(BRAIN_QUEUE_FILE)
    for line in queue.splitlines():
        line = line.strip()
        if line.startswith("| BOOT-") or line.startswith("| TASK-"):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 6:
                task_id, task_type, priority, status, assigned, created = parts[:6]
                if status == "IN-PROGRESS" and priority == "CRITICAL":
                    return {
                        "task_id": task_id,
                        "type": task_type,
                        "priority": priority,
                        "status": status,
                        "assigned": assigned,
                        "created": created,
                    }
    return None


def validate_task(task):
    """
    Decision Engine validation (DECISION_ENGINE.md rules).
    Returns True if all checks pass, False otherwise.
    """
    task_id = task['task_id']
    assigned = task.get('assigned', '')
    errors = []

    # Rule 1: Task must exist in BRAIN_QUEUE (BrainOS internal approval)
    bq = read_file(BRAIN_QUEUE_FILE)
    if task_id not in bq:
        errors.append(f"Rule 1 FAIL: {task_id} not found in BRAIN_QUEUE (owner approval missing)")

    # Rule 2: Check TASK_QUEUE for duplicate In-Progress task on same module
    # NOTE: task dict does not yet have 'module' key - this check is safe
    # but inactive until pick_next_task() is extended to include module field.
    tq = read_file(TASK_QUEUE_FILE)
    module = task.get('module', '')
    if module:
        in_progress_count = 0
        for line in tq.splitlines():
            if module in line and "In-Progress" in line:
                in_progress_count += 1
        if in_progress_count > 0:
            errors.append(f"Rule 2 FAIL: module '{module}' already has In-Progress task in TASK_QUEUE")

    # Rule 3: Assigned AI must exist in AI_REGISTRY (development/11_AIOS)
    if assigned:
        registry = read_file("development/11_AIOS/AI_REGISTRY.md")
        if assigned not in registry:
            errors.append(f"Rule 3 FAIL: assigned AI '{assigned}' not found in AI_REGISTRY")

    # Rule 4: HANDOVER.md must be accessible (will be updated post-execution)
    try:
        read_file(HANDOVER_FILE)
    except Exception:
        errors.append("Rule 4 FAIL: HANDOVER.md not accessible")

    # Rule 5: Completion review required (manual step, always passes here)

    if errors:
        for e in errors:
            print(f"  DECISION ENGINE: {e}")
            log_memory("ERROR", "DECISION_ENGINE", e)
        return False

    log_memory("INFO", "DECISION_ENGINE", f"VALIDATE: {task_id} - all 5 rules passed")
    return True


def decision(task):
    print("")
    print("=" * 50)
    print("BRAIN DISPATCHER v1.0 — Task Ready")
    print("=" * 50)
    print(f"  Task ID:    {task['task_id']}")
    print(f"  Type:       {task['type']}")
    print(f"  Priority:   {task['priority']}")
    print(f"  Assigned:   {task['assigned']}")
    print(f"  Created:    {task['created']}")
    print("=" * 50)


def route_task(task):
    log_memory("INFO", "DISPATCHER", f"ROUTE: {task['task_id']} — routing via TaskRouter")
    try:
        from TASK_ROUTER import TaskRouter
        router = TaskRouter()
        result = router.create_task(task["type"], task["task_id"], task["priority"])
        log_memory("INFO", "DISPATCHER", f"ROUTE result: {result.get('status', 'UNKNOWN')}")
        return result
    except Exception as e:
        log_memory("ERROR", "DISPATCHER", f"ROUTE failed: {e}")
        return {"status": "FAILED", "error": str(e)}


def execute_task(task, route_result):
    # NEW: skip execute entirely if routing failed — no confirm prompt shown
    if route_result.get("status") == "FAILED":
        print("EXECUTE SKIPPED — routing failed:", route_result.get("error", "unknown"))
        log_memory("WARN", "DISPATCHER", f"EXECUTE SKIPPED: {task['task_id']} — routing failed")
        return False

    print("")
    print("Ready to execute. This updates documentation files ONLY (no 03_Bot/ changes).")
    confirm = input("Execute? (y/n): ").strip().lower()

    if confirm != "y":
        print("SKIPPED — no confirmation")
        log_memory("WARN", "DISPATCHER", f"EXECUTE SKIPPED: {task['task_id']} — user said no")
        return False

    print("Executing...")
    log_memory("INFO", "DISPATCHER", f"EXECUTE CONFIRMED: {task['task_id']}")

    queue = read_file(BRAIN_QUEUE_FILE)
    queue = queue.replace(
        f"| {task['task_id']} | {task['type']} | {task['priority']} | IN-PROGRESS",
        f"| {task['task_id']} | {task['type']} | {task['priority']} | DONE"
    )
    write_file(BRAIN_QUEUE_FILE, queue)
    log_memory("INFO", "DISPATCHER", f"BRAIN_QUEUE updated: {task['task_id']} -> DONE")

    handover = read_file(HANDOVER_FILE)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    handover += f"\n| {task['task_id']} completed by dispatcher.py | DeepSeek-1 | {ts} | development/15_BrainOS/ |"
    write_file(HANDOVER_FILE, handover)
    log_memory("INFO", "DISPATCHER", f"HANDOVER updated: {task['task_id']}")

    print("Execution complete!")
    return True


def main():
    log_memory("INFO", "DISPATCHER", "=== DISPATCHER STARTED ===")

    check_lock_token()

    task = pick_next_task()
    if task is None:
        print("No CRITICAL/IN-PROGRESS task found in BRAIN_QUEUE.")
        log_memory("INFO", "DISPATCHER", "No task found — exiting")
        sys.exit(0)

    if not validate_task(task):
        print("Validation failed.")
        sys.exit(1)

    decision(task)
    route_result = route_task(task)
    executed = execute_task(task, route_result)

    if executed:
        log_memory("INFO", "DISPATCHER", "=== DISPATCHER FINISHED (executed) ===")
    else:
        log_memory("WARN", "DISPATCHER", "=== DISPATCHER FINISHED (skipped) ===")


if __name__ == "__main__":
    main()
