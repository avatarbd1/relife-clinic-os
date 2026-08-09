#!/usr/bin/env python3
"""Convert safely-claimed TaskInbox text files into BrainOS queue entries."""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "development/15_AI_Brain"))
sys.path.insert(0, str(REPO_ROOT / "development/15_AI_Brain" / "Control"))
sys.path.insert(0, str(REPO_ROOT / "development/15_AI_Brain" / "Core"))
os.chdir(REPO_ROOT)

from add_task import classify, save_description  # noqa: E402
from concurrency_lock import BrainOSLock, LockBusyError  # noqa: E402
from task_router_bridge import TaskRouterBridge  # noqa: E402

INBOX_DIR = REPO_ROOT / "development/15_BrainOS" / "TaskInbox"
PROCESSING_DIR = INBOX_DIR / "processing"
PROCESSED_DIR = INBOX_DIR / "processed"
FAILED_DIR = INBOX_DIR / "failed"
MEMORY_PATH = REPO_ROOT / "development/15_BrainOS" / "BRAIN_MEMORY.md"
MAX_FILE_BYTES = 64 * 1024
MAX_FILES_PER_SCAN = 10


def log_memory(message: str, level: str = "INFO") -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with MEMORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] [{level}] [TASK_DETECTOR] {message}\n")


def _archive_path(directory: Path, original_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = directory / f"{timestamp}_{original_name}"
    if candidate.exists():
        candidate = directory / f"{timestamp}_{uuid4().hex[:8]}_{original_name}"
    return candidate


def claim_file(path: Path) -> Path:
    """Atomically remove a file from the visible inbox before processing it."""
    PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
    claimed = PROCESSING_DIR / f"{uuid4().hex}_{path.name}"
    path.replace(claimed)
    return claimed


def process_claimed_file(
    path: Path,
    bridge: TaskRouterBridge,
    classify_func: Callable[[str], dict] = classify,
    save_func: Callable[..., None] = save_description,
) -> tuple[bool, str]:
    if path.stat().st_size > MAX_FILE_BYTES:
        return False, f"file exceeds {MAX_FILE_BYTES} byte limit"

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return False, "empty file"

    result = classify_func(text)
    task = bridge.create_and_persist_task(
        result["type"], result["description"], result["priority"]
    )
    if task.get("status") != "PROVIDER_ASSIGNED":
        return False, task.get("error", "task creation failed")

    task_id = task["task_id"]
    save_func(task_id, result["description"], text, result.get("target_file", ""))
    log_memory(
        f"AUTO-DETECTED: {task_id} from {path.name} "
        f"(type={result['type']}, priority={result['priority']})"
    )
    return True, task_id


def run_scan(
    bridge: TaskRouterBridge | None = None,
    classify_func: Callable[[str], dict] = classify,
    save_func: Callable[..., None] = save_description,
) -> tuple[int, int]:
    for directory in (INBOX_DIR, PROCESSING_DIR, PROCESSED_DIR, FAILED_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    files = sorted(INBOX_DIR.glob("*.txt"))[:MAX_FILES_PER_SCAN]
    if not files:
        print("No new files in TaskInbox/.")
        return 0, 0

    bridge = bridge or TaskRouterBridge()
    succeeded = failed = 0

    for inbox_path in files:
        original_name = inbox_path.name
        try:
            claimed = claim_file(inbox_path)
        except FileNotFoundError:
            continue

        try:
            ok, detail = process_claimed_file(
                claimed, bridge, classify_func=classify_func, save_func=save_func
            )
        except Exception as exc:
            ok, detail = False, str(exc)

        destination_dir = PROCESSED_DIR if ok else FAILED_DIR
        destination = _archive_path(destination_dir, original_name)
        shutil.move(str(claimed), str(destination))

        if ok:
            succeeded += 1
            print(f"QUEUED {detail} from {original_name}")
        else:
            failed += 1
            print(f"FAILED {original_name}: {detail}")
            log_memory(f"AUTO-DETECT FAILED: {original_name} — {detail}", level="ERROR")

    return succeeded, failed


def main() -> int:
    try:
        with BrainOSLock():
            succeeded, failed = run_scan()
    except LockBusyError as exc:
        print(f"SKIPPED: {exc}")
        return 0

    print(f"Task detector complete: queued={succeeded}, failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
