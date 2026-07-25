#!/usr/bin/env python3
"""
DISPATCHER_BRIDGE — Connects BRAIN_DISPATCHER to Task Router Bridge
This is the main execution entry point for Phase 1 Step 7+
"""

import sys
import os

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain"))
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Control"))

from task_router_bridge import TaskRouterBridge
from self_healing_bridge import SelfHealingBridge
from datetime import datetime

MAX_TASKS_PER_RUN = 3  # Queue Rule: max 3 concurrent tasks total
PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}


def pick_next_queued(rows, active_critical_count):
    """Pick the next QUEUED row to dispatch, honoring:
    - Queue Rule 1: max 1 CRITICAL task active at a time
    - Priority order: CRITICAL > HIGH > NORMAL > LOW
    """
    queued = [r for r in rows if r["status"] == "QUEUED"]
    queued.sort(key=lambda r: PRIORITY_ORDER.get(r["priority"].upper(), 9))
    for row in queued:
        if row["priority"].upper() == "CRITICAL" and active_critical_count >= 1:
            continue
        return row
    return None


def process_task(bridge, row):
    """Run one queued row through ROUTE -> EXECUTE -> LOG -> UPDATE -> HANDOVER
    (BRAIN_DISPATCHER.md steps 5-9), reusing the existing ProviderRouter
    (already wired for real Groq/OpenRouter/Gemini calls since Step 6)."""
    in_progress_line = bridge.set_queue_row_status(row["raw_line"], "IN-PROGRESS")
    bridge.log_memory(f"DISPATCH: {row['task_id']} ({row['type']}, {row['priority']}) -> IN-PROGRESS")

    result = bridge.router.provider_router.route(row["task_id"], row["type"], row["priority"])

    if result["status"] == "SUCCESS":
        provider = result["selected_provider"]
        bridge.move_queue_row(in_progress_line, "DONE", section="Completed", provider=provider)
        bridge.log_memory(
            f"EXECUTE SUCCESS: {row['task_id']} -> {provider} "
            f"(attempts={result['attempts']}, fallback={result.get('fallback_used')})"
        )
        bridge.update_handover(
            row["task_id"], "AUTO-DONE",
            f"Type: {row['type']}, Provider: {provider}, via autonomous loop (Step 10)"
        )
        return True, result

    # Queue Rule 4: failed tasks auto-retry 1x, then escalate to HANDOVER
    bridge.log_memory(f"EXECUTE FAILED (attempt 1): {row['task_id']} — {result.get('error')}", level="WARN")
    retry = bridge.router.provider_router.route(row["task_id"], row["type"], row["priority"])

    if retry["status"] == "SUCCESS":
        provider = retry["selected_provider"]
        bridge.move_queue_row(in_progress_line, "DONE", section="Completed", provider=provider)
        bridge.log_memory(f"EXECUTE SUCCESS on retry: {row['task_id']} -> {provider}")
        bridge.update_handover(
            row["task_id"], "AUTO-DONE (retry)",
            f"Type: {row['type']}, Provider: {provider}, via autonomous loop retry (Step 10)"
        )
        return True, retry

    bridge.move_queue_row(in_progress_line, "FAILED", section="Failed / Blocked", provider=row["assigned"])
    bridge.log_memory(
        f"EXECUTE FAILED after retry: {row['task_id']} — escalating to HANDOVER", level="ERROR"
    )
    bridge.update_handover(
        row["task_id"], "AUTO-FAILED",
        f"Type: {row['type']} — failed after 1 retry ({retry.get('error')}), needs manual review (Step 10 autonomous loop)"
    )
    return False, retry


def main():
    print("=" * 50)
    print("BRAIN DISPATCHER + TASK ROUTER BRIDGE")
    print("Step 10/10: Full Autonomous Loop")
    print("=" * 50)

    # Step 0 (Step 9/10): self-healing pre-flight gate — abort dispatch
    # if required BrainOS structure/keys are missing. Read-only check,
    # never touches 03_Bot/.
    print("\n🩺 Running self-healing pre-flight check...")
    healing = SelfHealingBridge()
    healthy, health_result = healing.preflight()
    if healthy:
        print("   ✅ Pre-flight check passed — proceeding with dispatch.")
    else:
        print("   ⚠️ Pre-flight check found issues — dispatch aborted.")
        if health_result["missing_required"]:
            print(f"      Missing required: {health_result['missing_required']}")
        if health_result["missing_keys"]:
            print(f"      Missing keys: {health_result['missing_keys']}")
        print("   See 15_AI_Brain/Monitor/HEALTH_REPORT.md for details.")
        return

    bridge = TaskRouterBridge()

    # Dispatch Rule: only dispatch if LOCK_TOKEN = FREE
    lock = bridge.get_lock_token()
    if lock and lock.upper() != "FREE":
        print(f"\n🔒 BRAIN_STATE Lock Token is '{lock}' — another session may be active.")
        print("   Dispatch aborted (Dispatch Rule: only dispatch if LOCK_TOKEN = FREE).")
        return

    bridge.set_lock_token("BUSY")
    try:
        print("\n📥 Reading BRAIN_QUEUE Active Queue...")
        rows = bridge.get_active_queue_rows()
        queued_count = sum(1 for r in rows if r["status"] == "QUEUED")
        print(f"   Found {len(rows)} active-queue row(s), {queued_count} QUEUED")

        active_critical = sum(
            1 for r in rows if r["status"] == "IN-PROGRESS" and r["priority"].upper() == "CRITICAL"
        )

        processed, succeeded, failed = 0, 0, 0
        last_task_id = None

        while processed < MAX_TASKS_PER_RUN:
            rows = bridge.get_active_queue_rows()
            next_row = pick_next_queued(rows, active_critical)
            if next_row is None:
                break

            print(f"\n▶️  [{processed + 1}/{MAX_TASKS_PER_RUN}] Dispatching {next_row['task_id']} "
                  f"({next_row['type']}, {next_row['priority']})")
            if next_row["priority"].upper() == "CRITICAL":
                active_critical += 1

            ok, result = process_task(bridge, next_row)
            last_task_id = next_row["task_id"]
            processed += 1
            if ok:
                succeeded += 1
                print(f"   ✅ DONE via {result.get('selected_provider')}")
            else:
                failed += 1
                print(f"   ❌ FAILED — {result.get('error')}")

        if last_task_id:
            bridge.update_brain_state(last_task_id)

        print("\n" + "-" * 50)
        if processed == 0:
            print("📭 No QUEUED tasks found — nothing to dispatch this run.")
        else:
            print(f"📊 Processed {processed} task(s) this run: {succeeded} done, {failed} failed.")
        print("-" * 50)

    finally:
        bridge.set_lock_token("FREE")
        print("\n🔓 Lock Token released (FREE).")

    print("\n" + "=" * 50)
    print("STEP 10 RUN COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()
