#!/usr/bin/env python3
"""
task_result_logger.py — BrainOS Phase 2, Item 4: Task Result Logger
Relife Clinic OS

Permanent structured audit trail for every task execution.
Writes to: 15_AI_Brain/Logs/TASK_RESULTS.jsonl
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
if os.path.isdir(REPO_ROOT):
    os.chdir(REPO_ROOT)

LOG_DIR = Path("15_AI_Brain/Logs")
LOG_FILE = LOG_DIR / "TASK_RESULTS.jsonl"


class TaskResultLogger:
    """Structured JSONL logger for task execution history."""

    def __init__(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if not LOG_FILE.exists():
            LOG_FILE.write_text("", encoding="utf-8")

    def log(
        self,
        task_id: str,
        task_type: str,
        priority: str,
        provider: str,
        prompt: str,
        output: Optional[str],
        validation_result: Optional[Dict],
        confirm_gate_result: Optional[Dict],
        status: str,
        error: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        fallback_used: bool = False,
        retry_count: int = 0,
    ) -> Dict:
        """Log one task execution result as a single JSONL line."""

        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "task_type": task_type,
            "priority": priority,
            "provider": provider,
            "prompt_preview": prompt[:500] if prompt else None,
            "output_preview": output[:500] if output else None,
            "output_full_path": None,
            "validation": validation_result,
            "confirm_gate": confirm_gate_result,
            "status": status,
            "error": error,
            "execution_time_ms": execution_time_ms,
            "fallback_used": fallback_used,
            "retry_count": retry_count,
        }

        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            logger.info(f"[TaskResultLogger] Logged {task_id} -> {status}")
        except Exception as e:
            logger.error(f"[TaskResultLogger] Failed to write log: {e}")
            entry["_log_write_error"] = str(e)

        return entry

    def log_output_file(self, task_id: str, file_path: str):
        """Update the most recent entry for task_id with the output file path."""
        if not LOG_FILE.exists():
            return

        lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
        updated = False
        for i in range(len(lines) - 1, -1, -1):
            try:
                entry = json.loads(lines[i])
                if entry.get("task_id") == task_id and entry.get("output_full_path") is None:
                    entry["output_full_path"] = file_path
                    lines[i] = json.dumps(entry, ensure_ascii=False)
                    updated = True
                    break
            except json.JSONDecodeError:
                continue

        if updated:
            LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def get_history(self, task_id: Optional[str] = None, limit: int = 100) -> list:
        """Read log entries. Optionally filter by task_id."""
        if not LOG_FILE.exists():
            return []

        entries = []
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if task_id is None or entry.get("task_id") == task_id:
                        entries.append(entry)
                except json.JSONDecodeError:
                    continue

        return entries[-limit:]

    def stats(self) -> Dict:
        """Return aggregate stats from the log."""
        entries = self.get_history(limit=10000)
        total = len(entries)
        success = sum(1 for e in entries if e.get("status") == "SUCCESS")
        failed = sum(1 for e in entries if e.get("status") == "FAILED")
        blocked = sum(1 for e in entries if e.get("status") == "BLOCKED")
        fallback = sum(1 for e in entries if e.get("fallback_used"))

        provider_counts = {}
        for e in entries:
            p = e.get("provider", "unknown")
            provider_counts[p] = provider_counts.get(p, 0) + 1

        return {
            "total_tasks": total,
            "success": success,
            "failed": failed,
            "blocked": blocked,
            "fallback_used": fallback,
            "provider_distribution": provider_counts,
            "last_updated": datetime.now().isoformat(),
        }


def _cli():
    import argparse
    parser = argparse.ArgumentParser(description="BrainOS Task Result Logger")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("stats")
    p_history = sub.add_parser("history")
    p_history.add_argument("--task-id", default=None)
    p_history.add_argument("--limit", type=int, default=20)

    args = parser.parse_args()
    logger = TaskResultLogger()

    if args.command == "stats":
        print(json.dumps(logger.stats(), indent=2, ensure_ascii=False))
    elif args.command == "history":
        entries = logger.get_history(task_id=args.task_id, limit=args.limit)
        for e in entries:
            ts = e["timestamp"][:19]
            print(f"[{ts}] {e['task_id']} | {e['task_type']} | {e['status']} | {e.get('provider', 'N/A')}")
    else:
        parser.print_help()


if __name__ == "__main__":
    print("=== Task Result Logger Self-Test ===\n")
    trl = TaskResultLogger()

    r1 = trl.log(
        task_id="LOG-TEST-001",
        task_type="Documentation",
        priority="NORMAL",
        provider="openrouter",
        prompt="Write a README for the project",
        output="# Project README\n\nThis is a test.",
        validation_result={"valid": True, "checks": []},
        confirm_gate_result=None,
        status="SUCCESS",
        execution_time_ms=1200,
    )
    print(f"Logged success: {r1['task_id']} -> {r1['status']}")

    r2 = trl.log(
        task_id="LOG-TEST-002",
        task_type="Python Coding",
        priority="CRITICAL",
        provider="groq",
        prompt="Write a Python function",
        output=None,
        validation_result=None,
        confirm_gate_result=None,
        status="FAILED",
        error="API key invalid",
        fallback_used=True,
        retry_count=1,
    )
    print(f"Logged failure: {r2['task_id']} -> {r2['status']}")

    stats = trl.stats()
    print(f"\nStats: {stats}")
    assert stats["total_tasks"] >= 2
    assert stats["success"] >= 1
    assert stats["failed"] >= 1

    history = trl.get_history(limit=10)
    print(f"\nHistory entries: {len(history)}")

    print("\nALL TASK RESULT LOGGER SELF-TESTS PASSED")
