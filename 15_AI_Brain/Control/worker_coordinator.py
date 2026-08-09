#!/usr/bin/env python3
"""BrainOS Phase 3 worker coordination.

Coordinates human-facing AI worker IDs from ``11_AIOS/AI_REGISTRY.md``
against the shared ``13_AI_Tasks/TASK_QUEUE.md``.  Provider routing remains a
separate concern: this module prevents two AI workers from claiming the same
work before execution starts.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
CONTROL_DIR = Path(__file__).resolve().parent
if str(CONTROL_DIR) not in sys.path:
    sys.path.insert(0, str(CONTROL_DIR))

from concurrency_lock import BrainOSLock, LockBusyError  # noqa: E402


class CoordinationError(RuntimeError):
    """Raised when an assignment would violate coordination rules."""


@dataclass(frozen=True)
class Worker:
    worker_id: str
    platform: str
    module: str = ""
    status: str = ""


@dataclass(frozen=True)
class ActiveTask:
    task: str
    worker_id: str
    started: str
    module: str


@dataclass(frozen=True)
class CoordinationEvent:
    event: str
    worker_id: str
    event_date: str
    details: str


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _section_lines(text: str, heading: str) -> list[str]:
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        return []
    body = text[start + len(marker) :]
    next_heading = body.find("\n## ")
    if next_heading >= 0:
        body = body[:next_heading]
    return body.splitlines()


def _data_rows(lines: Iterable[str], columns: int) -> list[list[str]]:
    rows = []
    for line in lines:
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if len(cells) != columns:
            continue
        joined = "".join(cells)
        if set(joined) <= {"-", ":"}:
            continue
        if cells[0] in {"কাজ", "ID", "Task", "Task ID"}:
            continue
        rows.append(cells)
    return rows


def modules_overlap(left: str, right: str) -> bool:
    """Return True when module/file targets are equal or parent/child paths."""
    a = left.strip().rstrip("/")
    b = right.strip().rstrip("/")
    if not a or not b:
        return False
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


class WorkerCoordinator:
    def __init__(
        self,
        registry: Path | None = None,
        queue: Path | None = None,
        handover: Path | None = None,
        lock_path: Path | None = None,
        brain_queue: Path | None = None,
    ) -> None:
        self.registry = registry or ROOT / "11_AIOS" / "AI_REGISTRY.md"
        self.queue = queue or ROOT / "13_AI_Tasks" / "TASK_QUEUE.md"
        self.handover = handover or ROOT / "12_Handover" / "HANDOVER.md"
        self.lock_path = lock_path or ROOT / "15_AI_Brain" / "Logs" / "brainos.lock"
        self.brain_queue = brain_queue or ROOT / "15_BrainOS" / "BRAIN_QUEUE.md"

    def brain_active_task_ids(self) -> set[str]:
        """Return task IDs currently present in BrainOS Active Queue."""
        if not self.brain_queue.exists():
            raise CoordinationError(f"BrainOS queue not found: {self.brain_queue}")
        text = self.brain_queue.read_text(encoding="utf-8")
        rows = _data_rows(_section_lines(text, "Active Queue"), 6)
        return {row[0] for row in rows}

    def reconciliation_issues(
        self,
        max_age_days: int = 7,
        as_of: date | None = None,
    ) -> list[tuple[ActiveTask, list[str]]]:
        """Detect inconsistent/stale claims without mutating either queue."""
        if max_age_days < 0:
            raise CoordinationError("max_age_days must be >= 0")

        active_ids = self.brain_active_task_ids()
        today = as_of or date.today()
        issues = []

        for item in self.active_tasks():
            reasons = []

            if item.task not in active_ids:
                reasons.append("missing from BRAIN_QUEUE Active Queue")

            try:
                started = date.fromisoformat(item.started)
                age_days = (today - started).days
                if age_days > max_age_days:
                    reasons.append(
                        f"claim age {age_days} days exceeds {max_age_days}-day threshold"
                    )
            except ValueError:
                reasons.append(f"invalid start date: {item.started}")

            if reasons:
                issues.append((item, reasons))

        return issues

    def workers(self) -> list[Worker]:
        text = self.registry.read_text(encoding="utf-8")
        result = []
        registry_lines = _section_lines(text, "ID তালিকা")
        if not registry_lines:
            raise CoordinationError("AI_REGISTRY.md has no ID তালিকা section")
        for row in _data_rows(registry_lines, 4):
            worker_id, platform, module, status = row
            if "-" not in worker_id:
                continue
            if status.lower() in {"inactive", "disabled", "blocked"}:
                continue
            result.append(Worker(worker_id, platform, module, status))
        return result

    def active_tasks(self) -> list[ActiveTask]:
        text = self.queue.read_text(encoding="utf-8")
        rows = _data_rows(_section_lines(text, "In-Progress"), 4)
        return [ActiveTask(*row) for row in rows]

    def recent_events(self, limit: int = 5) -> list[CoordinationEvent]:
        """Return the newest coordination rows from HANDOVER.md."""
        if limit < 0:
            raise CoordinationError("event limit must be >= 0")
        if limit == 0 or not self.handover.exists():
            return []

        rows = _data_rows(self.handover.read_text(encoding="utf-8").splitlines(), 4)
        events = [CoordinationEvent(*row) for row in rows]
        return list(reversed(events[-limit:]))

    def dashboard_lines(
        self,
        max_age_days: int = 7,
        event_limit: int = 5,
    ) -> list[str]:
        """Build a read-only coordination health snapshot for operators."""
        active = self.active_tasks()
        free = self.available_workers()
        issues = self.reconciliation_issues(max_age_days)
        events = self.recent_events(event_limit)

        lines = [
            "=== AI WORKER COORDINATION DASHBOARD ===",
            f"Active assignments: {len(active)}",
        ]
        lines.extend(
            f"  {item.worker_id}: {item.task} [{item.module}]"
            for item in active
        )
        lines.append(f"Available workers: {len(free)}")
        lines.append("  " + (", ".join(worker.worker_id for worker in free) or "none"))
        lines.append(f"Reconciliation health: {'HEALTHY' if not issues else 'ISSUES'}")
        lines.append(f"Reconciliation issues: {len(issues)}")
        for item, reasons in issues:
            lines.append(
                f"  {item.task} | {item.worker_id} | {'; '.join(reasons)}"
            )
        lines.append(f"Recent coordination events: {len(events)}")
        lines.extend(
            f"  {event.event_date} | {event.worker_id} | {event.event} | {event.details}"
            for event in events
        )
        return lines

    def available_workers(self, module: str = "") -> list[Worker]:
        busy = {task.worker_id for task in self.active_tasks()}
        free = [worker for worker in self.workers() if worker.worker_id not in busy]
        if not module:
            return free
        # Prefer a worker permanently associated with the requested module.
        return sorted(
            free,
            key=lambda worker: (not modules_overlap(worker.module, module), worker.worker_id),
        )

    def check_module(self, module: str) -> None:
        for task in self.active_tasks():
            if modules_overlap(task.module, module):
                raise CoordinationError(
                    f"module '{module}' conflicts with active task '{task.task}' "
                    f"held by {task.worker_id} ({task.module})"
                )

    def assign(self, task: str, module: str, worker_id: str | None = None) -> Worker:
        try:
            with BrainOSLock(self.lock_path):
                return self._assign_locked(task, module, worker_id)
        except LockBusyError as exc:
            raise CoordinationError(str(exc)) from exc

    def assign_locked(self, task: str, module: str, worker_id: str | None = None) -> Worker:
        """Assign when the caller already holds the shared BrainOS lock."""
        return self._assign_locked(task, module, worker_id)

    def _assign_locked(self, task: str, module: str, worker_id: str | None = None) -> Worker:
        self.check_module(module)
        available = self.available_workers(module)
        if worker_id:
            selected = next((w for w in available if w.worker_id == worker_id), None)
            if selected is None:
                registered = {w.worker_id for w in self.workers()}
                reason = "busy" if worker_id in {t.worker_id for t in self.active_tasks()} else "unavailable"
                if worker_id not in registered:
                    reason = "not registered"
                raise CoordinationError(f"worker '{worker_id}' is {reason}")
        else:
            if not available:
                raise CoordinationError("no AI worker is currently available")
            selected = available[0]

        text = self.queue.read_text(encoding="utf-8")
        original_text = text
        marker = "## In-Progress"
        start = text.find(marker)
        if start < 0:
            raise CoordinationError("TASK_QUEUE.md has no In-Progress section")
        next_heading = text.find("\n## ", start + len(marker))
        insert_at = len(text) if next_heading < 0 else next_heading
        row = f"| {task} | {selected.worker_id} | {date.today().isoformat()} | {module} |\n"
        text = text[:insert_at].rstrip() + "\n" + row + "\n" + text[insert_at:].lstrip("\n")
        self.queue.write_text(text, encoding="utf-8")
        try:
            self._handover(task, selected.worker_id, "ASSIGNED", module)
        except Exception as exc:
            try:
                self.queue.write_text(original_text, encoding="utf-8")
            except Exception as rollback_exc:
                raise CoordinationError(
                    f"assignment handover failed for '{task}' and queue rollback also failed: "
                    f"{rollback_exc}"
                ) from exc
            raise CoordinationError(
                f"assignment handover failed for '{task}'; queue claim rolled back: {exc}"
            ) from exc
        return selected

    def release_locked(self, task: str) -> ActiveTask | None:
        """Best-effort claim release for callers already holding the BrainOS lock."""
        text = self.queue.read_text(encoding="utf-8")
        active = next((item for item in self.active_tasks() if item.task == task), None)
        if active is None:
            return None

        lines = text.splitlines(keepends=True)
        in_progress = False
        removed = False

        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("## "):
                in_progress = stripped == "## In-Progress"
                continue
            if not in_progress or not stripped.startswith("|"):
                continue
            if _cells(line) == [
                active.task,
                active.worker_id,
                active.started,
                active.module,
            ]:
                del lines[index]
                removed = True
                break

        if not removed:
            raise CoordinationError(
                f"could not structurally release active task '{task}'"
            )

        self.queue.write_text("".join(lines), encoding="utf-8")
        return active

    def complete(self, task: str, evidence: str = "", review: bool = True) -> ActiveTask:
        try:
            with BrainOSLock(self.lock_path):
                return self._complete_locked(task, evidence, review)
        except LockBusyError as exc:
            raise CoordinationError(str(exc)) from exc

    def complete_locked(self, task: str, evidence: str = "", review: bool = True) -> ActiveTask:
        """Complete when the caller already holds the shared BrainOS lock."""
        return self._complete_locked(task, evidence, review)

    def _complete_locked(self, task: str, evidence: str = "", review: bool = True) -> ActiveTask:
        text = self.queue.read_text(encoding="utf-8")
        active = next((item for item in self.active_tasks() if item.task == task), None)
        if active is None:
            raise CoordinationError(f"active task '{task}' was not found")

        active_row = f"| {active.task} | {active.worker_id} | {active.started} | {active.module} |"
        if active_row not in text:
            raise CoordinationError(f"queue row for '{task}' changed during coordination")
        text = text.replace(active_row, "", 1)

        done_marker = "## Done"
        done_start = text.find(done_marker)
        if done_start < 0:
            raise CoordinationError("TASK_QUEUE.md has no Done section")
        next_heading = text.find("\n## ", done_start + len(done_marker))
        insert_at = len(text) if next_heading < 0 else next_heading
        done_row = f"| {task} | {active.worker_id} | {date.today().isoformat()} | {active.module} |\n"
        text = text[:insert_at].rstrip() + "\n" + done_row + "\n\n" + text[insert_at:].lstrip("\n")
        self.queue.write_text(text, encoding="utf-8")

        status = "REVIEW-READY" if review else "DONE"
        detail = evidence.strip() or "Evidence not supplied"
        self._handover(task, active.worker_id, status, f"{active.module}; {detail}")
        return active

    def _handover(self, task: str, worker_id: str, status: str, details: str) -> None:
        self.handover.parent.mkdir(parents=True, exist_ok=True)
        with self.handover.open("a", encoding="utf-8") as handle:
            handle.write(
                f"\n| {task} - {status} | {worker_id} | {date.today().isoformat()} | {details} |\n"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="BrainOS AI worker coordinator")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    assign = sub.add_parser("assign")
    assign.add_argument("task")
    assign.add_argument("module")
    assign.add_argument("--worker")
    complete = sub.add_parser("complete")
    complete.add_argument("task")
    complete.add_argument("--evidence", default="")
    complete.add_argument("--no-review", action="store_true")
    reconcile = sub.add_parser("reconcile")
    reconcile.add_argument("--max-age-days", type=int, default=7)
    dashboard = sub.add_parser("dashboard")
    dashboard.add_argument("--max-age-days", type=int, default=7)
    dashboard.add_argument("--event-limit", type=int, default=5)
    args = parser.parse_args()

    coordinator = WorkerCoordinator()
    try:
        if args.command == "status":
            active = coordinator.active_tasks()
            free = coordinator.available_workers()
            print(f"Active assignments: {len(active)}")
            for item in active:
                print(f"  {item.worker_id}: {item.task} [{item.module}]")
            print(f"Available workers: {len(free)}")
            print("  " + ", ".join(worker.worker_id for worker in free))
        elif args.command == "assign":
            worker = coordinator.assign(args.task, args.module, args.worker)
            print(f"Assigned {args.task} -> {worker.worker_id}")
        elif args.command == "complete":
            item = coordinator.complete(args.task, args.evidence, not args.no_review)
            print(f"Completed {item.task} by {item.worker_id}; handover updated")
        elif args.command == "reconcile":
            issues = coordinator.reconciliation_issues(args.max_age_days)
            print(f"Reconciliation issues: {len(issues)}")
            for item, reasons in issues:
                print(
                    f"  {item.task} | {item.worker_id} | {item.started} | "
                    f"{item.module} | {'; '.join(reasons)}"
                )
        else:
            print(
                "\n".join(
                    coordinator.dashboard_lines(
                        max_age_days=args.max_age_days,
                        event_limit=args.event_limit,
                    )
                )
            )
    except CoordinationError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
