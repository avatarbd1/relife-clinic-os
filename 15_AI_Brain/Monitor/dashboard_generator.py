#!/usr/bin/env python3
"""Generate the human-readable BrainOS operations dashboard."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MONITOR = ROOT / "15_AI_Brain" / "Monitor"
OUTPUT = MONITOR / "DASHBOARD.md"
CONTROL = ROOT / "15_AI_Brain" / "Control"
if str(CONTROL) not in sys.path:
    sys.path.insert(0, str(CONTROL))

from worker_coordinator import CoordinationError, WorkerCoordinator, modules_overlap  # noqa: E402


def _json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _queue_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    path = ROOT / "15_BrainOS" / "BRAIN_QUEUE.md"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return counts
    for line in lines:
        if not line.strip().startswith("|") or "TASK_ID" in line:
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 4 and not set(parts[0]) <= {"-", ":"}:
            status = parts[3].upper()
            counts[status] = counts.get(status, 0) + 1
    return counts


def _task_results() -> tuple[int, int, int]:
    total = success = failed = 0
    path = ROOT / "15_AI_Brain" / "Logs" / "TASK_RESULTS.jsonl"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0, 0, 0
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        status = str(row.get("status", "")).upper()
        success += status == "SUCCESS"
        failed += status == "FAILED"
    return total, success, failed


def _coordination_status(coordinator: WorkerCoordinator | None = None) -> dict:
    """Return a read-only Phase 3 coordination snapshot for the dashboard."""
    coordinator = coordinator or WorkerCoordinator()
    try:
        workers = coordinator.workers()
        active = coordinator.active_tasks()
        available = coordinator.available_workers()
    except (CoordinationError, OSError, ValueError) as exc:
        return {
            "status": "UNKNOWN",
            "workers": 0,
            "active": [],
            "available": 0,
            "conflicts": [],
            "error": str(exc),
        }

    conflicts = []
    for index, left in enumerate(active):
        for right in active[index + 1 :]:
            if left.worker_id == right.worker_id or modules_overlap(left.module, right.module):
                conflicts.append(f"{left.task} <-> {right.task}")

    return {
        "status": "CONFLICT" if conflicts else "OK",
        "workers": len(workers),
        "active": active,
        "available": len(available),
        "conflicts": conflicts,
        "error": "",
    }


def generate(coordinator: WorkerCoordinator | None = None) -> str:
    health = _json(MONITOR / "HEALTH_REPORT.json", {})
    required = health.get("required", [])
    env_keys = health.get("env_keys", [])
    missing_files = sum(not row.get("exists", False) for row in required)
    missing_keys = sum(row.get("status") == "missing" for row in env_keys)
    health_status = "HEALTHY" if health and missing_files == 0 and missing_keys == 0 else "ISSUES / UNKNOWN"

    counts = _queue_counts()
    total, success, failed = _task_results()
    coordination = _coordination_status(coordinator)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# BrainOS Operations Dashboard",
        f"_Generated: {now}_",
        "",
        "## Health",
        f"- Status: **{health_status}**",
        f"- Missing required files: {missing_files}",
        f"- Missing provider keys: {missing_keys}",
        "",
        "## Queue",
        f"- QUEUED: {counts.get('QUEUED', 0)}",
        f"- IN-PROGRESS: {counts.get('IN-PROGRESS', 0)}",
        f"- DONE: {counts.get('DONE', 0)}",
        f"- FAILED: {counts.get('FAILED', 0)}",
        "",
        "## Task Results",
        f"- Logged: {total}",
        f"- Success: {success}",
        f"- Failed: {failed}",
        "",
        "## AI Worker Coordination",
        f"- Status: **{coordination['status']}**",
        f"- Registered workers: {coordination['workers']}",
        f"- Active assignments: {len(coordination['active'])}",
        f"- Available workers: {coordination['available']}",
        f"- Conflicts: {len(coordination['conflicts'])}",
    ]
    for item in coordination["active"]:
        lines.append(f"  - {item.worker_id}: {item.task} [{item.module}]")
    for conflict in coordination["conflicts"]:
        lines.append(f"  - WARNING: {conflict}")
    if coordination["error"]:
        lines.append(f"  - Coordination data unavailable: {coordination['error']}")
    lines += [
        "",
        "_Auto-generated by `dashboard_generator.py`; do not edit manually._",
    ]
    text = "\n".join(lines) + "\n"
    OUTPUT.write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(generate(), end="")
