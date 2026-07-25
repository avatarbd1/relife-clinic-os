#!/usr/bin/env python3
"""task_result_logger.py — BrainOS Phase 2, Item 4: Structured JSONL logging for every task execution."""

import json, os, sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
LOG_FILE = Path(REPO_ROOT) / "15_AI_Brain" / "Logs" / "TASK_RESULTS.jsonl"

class TaskResultLogger:
    def __init__(self):
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: dict):
        record = {
            "timestamp": datetime.now().isoformat(),
            "task_id": entry.get("task_id", "UNKNOWN"),
            "provider": entry.get("provider", "unknown"),
            "status": entry.get("status", "UNKNOWN"),
            "input_summary": (entry.get("input", "") or "")[:200],
            "output_summary": (entry.get("output", "") or "")[:500],
            "validation": entry.get("validation", "skipped"),
            "confirm_gate": entry.get("confirm_gate", "bypassed"),
            "duration_sec": entry.get("duration_sec", 0),
            "retries": entry.get("retries", 0),
            "error": entry.get("error", ""),
        }
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")

    def tail(self, n=10):
        if not LOG_FILE.exists():
            return []
        with open(LOG_FILE) as f:
            lines = f.readlines()
        return [json.loads(l) for l in lines[-n:]]

if __name__ == "__main__":
    logger = TaskResultLogger()
    logger.log({
        "task_id": "TASK-TEST-001", "provider": "openrouter",
        "status": "DONE", "input": "Test log entry",
        "output": "OK", "validation": "passed",
        "confirm_gate": "auto", "duration_sec": 1.2
    })
    print("✅ Test logged. Last entry:", logger.tail(1))
