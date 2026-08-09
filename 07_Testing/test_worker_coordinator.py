import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "15_AI_Brain" / "Control" / "worker_coordinator.py"
SPEC = importlib.util.spec_from_file_location("worker_coordinator", MODULE_PATH)
worker_coordinator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = worker_coordinator
SPEC.loader.exec_module(worker_coordinator)


REGISTRY = """# Registry
## ID তালিকা
| ID | Platform | Module | Status |
|----|----------|--------|--------|
| ChatGPT-1 | ChatGPT | 15_AI_Brain | Active |
| Claude-1 | Claude | 03_Bot | |
| Gemini-1 | Gemini | | |
"""

QUEUE = """# Queue
## Pending
| কাজ | মডিউল/ফাইল | অগ্রাধিকার |
|-----|------------|------------|

## In-Progress
| কাজ | AI ID | শুরুর তারিখ | মডিউল/ফাইল |
|-----|-------|-------------|-------------|
| Existing | ChatGPT-1 | 2026-08-09 | 15_AI_Brain/Integration |

## Done
| কাজ | AI ID | তারিখ | মডিউল/ফাইল |
|-----|-------|-------|------------|
"""


BRAIN_QUEUE = """# Brain Queue
## Active Queue
| TASK_ID | Type | Priority | Status | Assigned | Created |
|---------|------|----------|--------|----------|---------|
| Existing | Testing | NORMAL | QUEUED | - | 2026-08-09 |
"""

class WorkerCoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.registry = root / "registry.md"
        self.queue = root / "queue.md"
        self.handover = root / "handover.md"
        self.lock = root / "brainos.lock"
        self.brain_queue = root / "brain_queue.md"
        self.registry.write_text(REGISTRY, encoding="utf-8")
        self.queue.write_text(QUEUE, encoding="utf-8")
        self.brain_queue.write_text(BRAIN_QUEUE, encoding="utf-8")
        self.coordinator = worker_coordinator.WorkerCoordinator(
            self.registry,
            self.queue,
            self.handover,
            self.lock,
            brain_queue=self.brain_queue,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_busy_worker_is_not_available(self):
        ids = {worker.worker_id for worker in self.coordinator.available_workers()}
        self.assertNotIn("ChatGPT-1", ids)
        self.assertEqual(ids, {"Claude-1", "Gemini-1"})

    def test_parent_child_module_conflict_is_blocked(self):
        with self.assertRaises(worker_coordinator.CoordinationError):
            self.coordinator.assign("Conflict", "15_AI_Brain/Integration/V2")

    def test_worker_can_hold_only_one_active_task(self):
        with self.assertRaises(worker_coordinator.CoordinationError):
            self.coordinator.assign("Second", "09_SOP", "ChatGPT-1")

    def test_assignment_is_blocked_while_brainos_lock_is_held(self):
        with worker_coordinator.BrainOSLock(self.lock):
            with self.assertRaises(worker_coordinator.CoordinationError):
                self.coordinator.assign("Locked", "09_SOP")

    def test_locked_lifecycle_works_when_caller_holds_brainos_lock(self):
        with worker_coordinator.BrainOSLock(self.lock):
            selected = self.coordinator.assign_locked("Phase5", "09_SOP")
            self.assertTrue(selected.worker_id)
            completed = self.coordinator.complete_locked("Phase5", "phase5 test")
            self.assertEqual(completed.task, "Phase5")

        self.assertNotIn(
            "Phase5",
            [item.task for item in self.coordinator.active_tasks()],
        )

    def test_assignment_handover_failure_rolls_back_claim(self):
        original = self.queue.read_text(encoding="utf-8")

        def fail_handover(*args, **kwargs):
            raise OSError("synthetic handover failure")

        original_handover = self.coordinator._handover
        self.coordinator._handover = fail_handover
        try:
            with self.assertRaises(worker_coordinator.CoordinationError):
                self.coordinator.assign("Rollback", "03_Bot/bot.py")
        finally:
            self.coordinator._handover = original_handover

        self.assertEqual(
            self.queue.read_text(encoding="utf-8"),
            original,
        )
        self.assertNotIn(
            "Rollback",
            [item.task for item in self.coordinator.active_tasks()],
        )

    def test_release_locked_removes_active_claim(self):
        self.coordinator.assign("ReleaseMe", "09_SOP", "Gemini-1")

        with worker_coordinator.BrainOSLock(self.lock):
            released = self.coordinator.release_locked("ReleaseMe")

        self.assertIsNotNone(released)
        self.assertEqual(released.task, "ReleaseMe")
        self.assertNotIn(
            "ReleaseMe",
            [item.task for item in self.coordinator.active_tasks()],
        )

    def test_reconcile_detects_orphan_and_stale_without_mutation(self):
        text = self.queue.read_text(encoding="utf-8")
        text = text.replace(
            "\n## Done",
            "\n| Orphan | Claude-1 | 2026-07-23 | 03_Bot/bot.py |\n\n## Done",
            1,
        )
        self.queue.write_text(text, encoding="utf-8")
        original = self.queue.read_text(encoding="utf-8")

        issues = self.coordinator.reconciliation_issues(
            max_age_days=7,
            as_of=worker_coordinator.date(2026, 8, 9),
        )

        orphan = next(
            (reasons for item, reasons in issues if item.task == "Orphan"),
            None,
        )
        self.assertIsNotNone(orphan)
        self.assertTrue(
            any("missing from BRAIN_QUEUE" in reason for reason in orphan)
        )
        self.assertTrue(any("claim age" in reason for reason in orphan))
        self.assertEqual(self.queue.read_text(encoding="utf-8"), original)

    def test_dashboard_reports_health_and_recent_events_without_mutation(self):
        self.handover.write_text(
            "# Handover\n"
            "| First - ASSIGNED | Claude-1 | 2026-08-08 | 03_Bot |\n"
            "| Second - REVIEW-READY | Gemini-1 | 2026-08-09 | tests passed |\n",
            encoding="utf-8",
        )
        queue_before = self.queue.read_text(encoding="utf-8")
        handover_before = self.handover.read_text(encoding="utf-8")

        lines = self.coordinator.dashboard_lines(
            max_age_days=7,
            event_limit=1,
        )

        report = "\n".join(lines)
        self.assertIn("Active assignments: 1", report)
        self.assertIn("Available workers: 2", report)
        self.assertIn("Reconciliation health: HEALTHY", report)
        self.assertIn("Recent coordination events: 1", report)
        self.assertIn("Second - REVIEW-READY", report)
        self.assertNotIn("First - ASSIGNED", report)
        self.assertEqual(self.queue.read_text(encoding="utf-8"), queue_before)
        self.assertEqual(self.handover.read_text(encoding="utf-8"), handover_before)

    def test_dashboard_rejects_negative_event_limit(self):
        with self.assertRaises(worker_coordinator.CoordinationError):
            self.coordinator.dashboard_lines(event_limit=-1)

    def test_assignment_prefers_matching_module_and_writes_handover(self):
        selected = self.coordinator.assign("Bot task", "03_Bot/bot.py")
        self.assertEqual(selected.worker_id, "Claude-1")
        queue = self.queue.read_text(encoding="utf-8")
        self.assertIn("| Bot task | Claude-1 |", queue)
        self.assertIn("Bot task - ASSIGNED", self.handover.read_text(encoding="utf-8"))

    def test_complete_releases_worker_and_marks_review_ready(self):
        self.coordinator.assign("Docs", "09_SOP", "Gemini-1")
        self.coordinator.complete("Docs", "tests passed")
        self.assertNotIn("Docs", [item.task for item in self.coordinator.active_tasks()])
        ids = {worker.worker_id for worker in self.coordinator.available_workers()}
        self.assertIn("Gemini-1", ids)
        handover = self.handover.read_text(encoding="utf-8")
        self.assertIn("Docs - REVIEW-READY", handover)
        self.assertIn("tests passed", handover)


if __name__ == "__main__":
    unittest.main()
