#!/usr/bin/env python3
"""
DISPATCHER_BRIDGE v2.0 — Full Autonomous Execution Loop
Connects BRAIN_DISPATCHER to Task Router Bridge + Task Executor + Validator + Logger
Phase 2: Real autonomous execution (Items 1, 3, 4 wired)
"""

import sys
import os
import time

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain"))
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Control"))
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Core"))
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Logs"))

from task_router_bridge import TaskRouterBridge
from self_healing_bridge import SelfHealingBridge
from task_executor import TaskExecutor
from output_validator import OutputValidator
from confirm_gate import ConfirmGate
from task_result_logger import TaskResultLogger
from alert_notifier import send_alert
from concurrency_lock import BrainOSLock, LockBusyError
from datetime import datetime

MAX_TASKS_PER_RUN = 3
PRIORITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}

PROMPT_TEMPLATES = {
    "Documentation": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Write technical documentation for the following topic.\n"
        "Topic: {description}\n"
        "Output: Markdown format, Bengali or English as appropriate."
    ),
    "Planning": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Create a detailed implementation plan.\n"
        "Topic: {description}\n"
        "Output: Step-by-step plan in Markdown."
    ),
    "Python Coding": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Write Python code for the following requirement.\n"
        "Requirement: {description}\n"
        "Rules: Use Python 3.12+, include docstrings, handle errors gracefully.\n"
        "Output: Only the Python code (no markdown fences needed if plain .py)."
    ),
    "Bug Fix": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Fix the following bug.\n"
        "Bug description: {description}\n"
        "Output: Fixed code with comments explaining the change."
    ),
    "Refactor": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Refactor the following code for clarity and performance.\n"
        "Description: {description}\n"
        "Output: Refactored code with improvement notes."
    ),
    "Testing": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Write test cases for the following module/feature.\n"
        "Feature: {description}\n"
        "Output: Python unittest or pytest code."
    ),
    "Automation": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Create an automation script or workflow.\n"
        "Description: {description}\n"
        "Output: Python or shell script with setup instructions."
    ),
    "Architecture": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Design system architecture for the following.\n"
        "Description: {description}\n"
        "Output: Markdown with diagrams (text-based) and component list."
    ),
    "Business Logic": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: Implement business logic for the following requirement.\n"
        "Requirement: {description}\n"
        "Output: Python code or pseudocode with logic explanation."
    ),
    "Default": (
        "You are an AI developer for Relife Clinic OS.\n"
        "Task: {description}\n"
        "Output: Appropriate code or documentation in Markdown."
    ),
}


MAX_FILE_CHARS = 40000  # প্রায় ১০,০০০ টোকেন, Groq-এর জন্য নিরাপদ সীমা

def _load_target_file_context(target_file: str) -> str:
    """target_file থাকলে তার আসল কোড পড়ে prompt-এ জুড়ে দেওয়ার
    জন্য একটা টেক্সট ব্লক বানায়। খুব বড় ফাইল হলে শুরুর অংশ + সতর্কবার্তা।"""
    if not target_file:
        return ""
    full_path = os.path.join(REPO_ROOT, target_file)
    if not os.path.exists(full_path):
        return ""
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            file_content = f.read()
    except Exception:
        return ""

    truncated_note = ""
    if len(file_content) > MAX_FILE_CHARS:
        file_content = file_content[:MAX_FILE_CHARS]
        truncated_note = (
            "\n\n[সতর্কতা: ফাইলটি অনেক বড়, শুধু প্রথম অংশ দেখানো হয়েছে। "
            "যদি প্রাসঙ্গিক অংশ এখানে না থাকে, output-এ স্পষ্ট করে বলো যে "
            "আরও context দরকার।]"
        )

    return (
        f"\n\nবর্তমান ফাইল ({target_file}) নিচে দেওয়া হলো — এই ফাইলের প্রেক্ষাপটে "
        f"কাজ করো। শুধু পরিবর্তিত/নতুন অংশটুকু স্পষ্ট comment সহ দাও (পুরো ফাইল "
        f"আবার লেখার দরকার নেই), এবং ঠিক কোন ফাংশন/লাইনের কাছে বসাতে হবে তা "
        f"উল্লেখ করো:\n\n```python\n{file_content}\n```{truncated_note}"
    )


def _build_prompt(task_type: str, description: str = "", target_file: str = "") -> str:
    template = PROMPT_TEMPLATES.get(task_type, PROMPT_TEMPLATES["Default"])
    desc = description or f"Complete the {task_type} task as per project standards."
    prompt = template.format(description=desc)
    prompt += _load_target_file_context(target_file)
    return prompt


def _output_path_for(task_id: str, task_type: str) -> str:
    ext_map = {
        "Python Coding": ".py",
        "Bug Fix": ".py",
        "Refactor": ".py",
        "Testing": ".py",
        "Automation": ".py",
        "Documentation": ".md",
        "Planning": ".md",
        "Architecture": ".md",
        "Business Logic": ".py",
    }
    ext = ext_map.get(task_type, ".md")
    return f"15_AI_Brain/Outputs/{task_id}{ext}"


def pick_next_queued(rows, active_critical_count):
    queued = [r for r in rows if r["status"] == "QUEUED"]
    queued.sort(key=lambda r: PRIORITY_ORDER.get(r["priority"].upper(), 9))
    for row in queued:
        if row["priority"].upper() == "CRITICAL" and active_critical_count >= 1:
            continue
        return row
    return None


def process_task(bridge, executor, validator, gate, logger, row):
    result = bridge.router.provider_router.route(row["task_id"], row["type"], row["priority"])

    if result["status"] != "SUCCESS":
        logger.log(
            task_id=row["task_id"],
            task_type=row["type"],
            priority=row["priority"],
            provider=result.get("selected_provider", "none"),
            prompt="",
            output=None,
            validation_result=None,
            confirm_gate_result=None,
            status="FAILED",
            error=f"Routing failed: {result.get('error')}",
            fallback_used=result.get("fallback_used", False),
            retry_count=result.get("retry_count", 0),
        )
        send_alert(
            "Provider routing failed",
            str(result.get("error", "Unknown routing error")),
            task_id=row["task_id"],
            stage="routing",
        )
        return False, result

    provider = result["selected_provider"]
    in_progress_line = bridge.set_queue_row_status(row["raw_line"], "IN-PROGRESS")
    bridge.log_memory(f"DISPATCH: {row['task_id']} ({row['type']}, {row['priority']}) -> IN-PROGRESS")

    prompt = _build_prompt(row["type"], row.get("description", ""), row.get("target_file", ""))
    output_path = _output_path_for(row["task_id"], row["type"])

    start_time = time.time()
    exec_result = executor.execute(
        task_id=row["task_id"],
        task_type=row["type"],
        prompt=prompt,
        output_path=output_path,
    )
    exec_time_ms = int((time.time() - start_time) * 1000)

    validation = None
    if exec_result.get("status") == "SUCCESS" and exec_result.get("output"):
        validation = validator.validate(exec_result["output"], output_path)
        if not validation.get("valid", False):
            exec_result["status"] = "FAILED"
            exec_result["error"] = "Validation failed: " + "; ".join(validation.get("errors", []))

    gate_result = None
    if exec_result.get("status") == "SUCCESS":
        gate_result = gate.propose(
            task_id=row["task_id"],
            content=exec_result["output"],
            target_path=output_path,
        )
        # আগে auto-approve হতো, এখন সব সময় owner রিভিউ করে approve করবে
        # (confirm_gate.py list / preview / approve <task_id> দিয়ে)
        gate_result["auto_approved"] = False

    logger.log(
        task_id=row["task_id"],
        task_type=row["type"],
        priority=row["priority"],
        provider=provider,
        prompt=prompt,
        output=exec_result.get("output"),
        validation_result=validation,
        confirm_gate_result=gate_result,
        status=exec_result.get("status", "UNKNOWN"),
        error=exec_result.get("error"),
        execution_time_ms=exec_time_ms,
        fallback_used=result.get("fallback_used", False),
        retry_count=exec_result.get("attempts", 0) - 1,
    )

    if exec_result.get("status") == "SUCCESS":
        bridge.move_queue_row(in_progress_line, "DONE", section="Completed", provider=provider)
        bridge.log_memory(
            f"EXECUTE SUCCESS: {row['task_id']} -> {provider} "
            f"(time={exec_time_ms}ms, valid={validation['valid'] if validation else 'N/A'})"
        )
        bridge.update_handover(
            row["task_id"], "AUTO-DONE",
            f"Type: {row['type']}, Provider: {provider}, ExecTime: {exec_time_ms}ms, "
            f"Valid: {validation['valid'] if validation else 'N/A'}, via autonomous loop v2"
        )
        return True, exec_result
    else:
        bridge.log_memory(f"EXECUTE FAILED (attempt 1): {row['task_id']} — {exec_result.get('error')}", level="WARN")
        retry_result = executor.execute(
            task_id=row["task_id"],
            task_type=row["type"],
            prompt=prompt,
            output_path=output_path,
        )
        retry_time_ms = int((time.time() - start_time) * 1000)

        if retry_result.get("status") == "SUCCESS":
            validation = validator.validate(retry_result["output"], output_path) if retry_result.get("output") else None
            if not validation or not validation.get("valid", False):
                retry_result["status"] = "FAILED"
                retry_result["error"] = "Validation failed: " + "; ".join(
                    validation.get("errors", []) if validation else ["empty output"]
                )
            else:
                gate_result = gate.propose(row["task_id"], retry_result["output"], output_path)
                gate_result["auto_approved"] = False

        if retry_result.get("status") == "SUCCESS":
            logger.log(
                task_id=row["task_id"],
                task_type=row["type"],
                priority=row["priority"],
                provider=provider,
                prompt=prompt,
                output=retry_result.get("output"),
                validation_result=validation,
                confirm_gate_result=gate_result,
                status="SUCCESS",
                execution_time_ms=retry_time_ms,
                fallback_used=True,
                retry_count=1,
            )
            bridge.move_queue_row(in_progress_line, "DONE", section="Completed", provider=provider)
            bridge.log_memory(f"EXECUTE SUCCESS on retry: {row['task_id']} -> {provider}")
            bridge.update_handover(row["task_id"], "AUTO-DONE (retry)",
                f"Type: {row['type']}, Provider: {provider}, via autonomous loop retry v2")
            return True, retry_result

        logger.log(
            task_id=row["task_id"],
            task_type=row["type"],
            priority=row["priority"],
            provider=provider,
            prompt=prompt,
            output=retry_result.get("output"),
            validation_result=None,
            confirm_gate_result=None,
            status="FAILED",
            error=retry_result.get("error", "Unknown error after retry"),
            execution_time_ms=retry_time_ms,
            fallback_used=True,
            retry_count=1,
        )
        bridge.move_queue_row(in_progress_line, "FAILED", section="Failed / Blocked", provider=row["assigned"])
        bridge.log_memory(f"EXECUTE FAILED after retry: {row['task_id']} — escalating to HANDOVER", level="ERROR")
        bridge.update_handover(
            row["task_id"], "AUTO-FAILED",
            f"Type: {row['type']} — failed after 1 retry ({retry_result.get('error')}), needs manual review"
        )
        send_alert(
            "Task failed after retry",
            str(retry_result.get("error", "Unknown execution error")),
            task_id=row["task_id"],
            stage="execution",
        )
        return False, retry_result


def _run_dispatcher():
    print("=" * 50)
    print("BRAIN DISPATCHER v2.0 — Full Autonomous Loop")
    print("Phase 2: Execute + Validate + Log + Confirm Gate")
    print("=" * 50)

    print("\nRunning self-healing pre-flight check...")
    healing = SelfHealingBridge()
    healthy, health_result = healing.preflight()
    if healthy:
        print(" Pre-flight check passed — proceeding with dispatch.")
    else:
        print(" Pre-flight check found issues — dispatch aborted.")
        if health_result["missing_required"]:
            print(f" Missing required: {health_result['missing_required']}")
        if health_result["missing_keys"]:
            print(f" Missing keys: {health_result['missing_keys']}")
        print(" See 15_AI_Brain/Monitor/HEALTH_REPORT.md for details.")
        send_alert(
            "Health pre-flight failed",
            f"missing_required={health_result['missing_required']}; missing_keys={health_result['missing_keys']}",
            stage="preflight",
        )
        return

    bridge = TaskRouterBridge()
    executor = TaskExecutor()
    validator = OutputValidator()
    gate = ConfirmGate()
    logger = TaskResultLogger()

    lock = bridge.get_lock_token()
    if lock and lock.upper() != "FREE":
        print(f"\n BRAIN_STATE Lock Token is '{lock}' — another session may be active.")
        print(" Dispatch aborted.")
        return

    bridge.set_lock_token("BUSY")
    try:
        print("\nReading BRAIN_QUEUE Active Queue...")
        rows = bridge.get_active_queue_rows()
        queued_count = sum(1 for r in rows if r["status"] == "QUEUED")
        print(f" Found {len(rows)} active-queue row(s), {queued_count} QUEUED")

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

            print(f"\n [{processed + 1}/{MAX_TASKS_PER_RUN}] Dispatching {next_row['task_id']} "
                  f"({next_row['type']}, {next_row['priority']})")
            if next_row["priority"].upper() == "CRITICAL":
                active_critical += 1

            ok, result = process_task(bridge, executor, validator, gate, logger, next_row)
            last_task_id = next_row["task_id"]
            processed += 1
            if ok:
                succeeded += 1
                print(f" DONE via {result.get('provider', result.get('selected_provider', 'unknown'))}")
            else:
                failed += 1
                print(f" FAILED — {result.get('error', 'Unknown')}")

        if last_task_id:
            bridge.update_brain_state(last_task_id)

        print("\n" + "-" * 50)
        if processed == 0:
            print(" No QUEUED tasks found — nothing to dispatch this run.")
        else:
            print(f" Processed {processed} task(s) this run: {succeeded} done, {failed} failed.")
        print("-" * 50)

        stats = logger.stats()
        print(f"\n Total task history: {stats['total_tasks']} (success={stats['success']}, failed={stats['failed']})")

    finally:
        bridge.set_lock_token("FREE")
        print("\n Lock Token released (FREE).")

    print("\n" + "=" * 50)
    print("DISPATCHER v2.0 RUN COMPLETE")
    print("=" * 50)


def main():
    """Run one dispatcher under an OS-level lock to prevent race conditions."""
    try:
        with BrainOSLock():
            _run_dispatcher()
    except LockBusyError as exc:
        print(f" Dispatch aborted: {exc}")
        send_alert("Concurrent run blocked", str(exc), stage="concurrency")


if __name__ == "__main__":
    main()
