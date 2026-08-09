#!/usr/bin/env python3
"""Tests for BrainOS Phase 4 coordination-aware dashboard automation."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MONITOR = ROOT / "15_AI_Brain" / "Monitor"
if str(MONITOR) not in sys.path:
    sys.path.insert(0, str(MONITOR))

import dashboard_generator as dashboard  # noqa: E402


class FakeCoordinator:
    def __init__(self, workers, active):
        self._workers = workers
        self._active = active

    def workers(self):
        return self._workers

    def active_tasks(self):
        return self._active

    def available_workers(self):
        busy = {item.worker_id for item in self._active}
        return [item for item in self._workers if item.worker_id not in busy]


class DashboardAutomationTests(unittest.TestCase):
    def test_coordination_snapshot_counts_workers(self):
        from worker_coordinator import Worker

        workers = [Worker("Claude-1", "Claude")]
        fake = FakeCoordinator(workers, [])
        status = dashboard._coordination_status(fake)
        self.assertEqual(status["status"], "OK")
        self.assertEqual(status["workers"], 1)
        self.assertEqual(status["available"], 1)

    def test_detects_same_module_conflict(self):
        from worker_coordinator import ActiveTask, Worker

        workers = [Worker("ChatGPT-1", "ChatGPT"), Worker("Claude-1", "Claude")]
        active = [
            ActiveTask("task-a", "ChatGPT-1", "2026-08-09", "15_AI_Brain/Control"),
            ActiveTask("task-b", "Claude-1", "2026-08-09", "15_AI_Brain/Control/file.py"),
        ]
        status = dashboard._coordination_status(FakeCoordinator(workers, active))
        self.assertEqual(status["status"], "CONFLICT")
        self.assertEqual(len(status["conflicts"]), 1)

    def test_detects_worker_double_assignment(self):
        from worker_coordinator import ActiveTask, Worker

        workers = [Worker("ChatGPT-1", "ChatGPT")]
        active = [
            ActiveTask("task-a", "ChatGPT-1", "2026-08-09", "module-a"),
            ActiveTask("task-b", "ChatGPT-1", "2026-08-09", "module-b"),
        ]
        status = dashboard._coordination_status(FakeCoordinator(workers, active))
        self.assertEqual(status["status"], "CONFLICT")

    def test_missing_registry_is_nonfatal(self):
        from worker_coordinator import WorkerCoordinator

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            coordinator = WorkerCoordinator(
                registry=base / "missing.md",
                queue=base / "queue.md",
                handover=base / "handover.md",
                lock_path=base / "lock",
            )
            status = dashboard._coordination_status(coordinator)
        self.assertEqual(status["status"], "UNKNOWN")
        self.assertTrue(status["error"])

    def test_generated_dashboard_includes_coordination_section(self):
        from worker_coordinator import Worker

        old_output = dashboard.OUTPUT
        with tempfile.TemporaryDirectory() as tmp:
            dashboard.OUTPUT = Path(tmp) / "DASHBOARD.md"
            try:
                text = dashboard.generate(FakeCoordinator([Worker("Claude-1", "Claude")], []))
            finally:
                dashboard.OUTPUT = old_output
        self.assertIn("## AI Worker Coordination", text)
        self.assertIn("# BrainOS Operations Dashboard", text)
        self.assertIn("Registered workers: 1", text)
        self.assertIn("Status: **OK**", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
