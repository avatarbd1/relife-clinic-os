import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "15_AI_Brain" / "Control" / "dispatcher_bridge.py"

SPEC = importlib.util.spec_from_file_location("dispatcher_phase5", MODULE_PATH)
dispatcher = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = dispatcher
SPEC.loader.exec_module(dispatcher)


ROW = {
    "task_id": "TASK-PHASE5",
    "type": "Testing",
    "priority": "NORMAL",
    "status": "QUEUED",
    "target_file": "03_Bot/bot.py",
    "assigned": "-",
    "raw_line": "| TASK-PHASE5 | Testing | NORMAL | QUEUED |",
}


class DispatcherCoordinationTests(unittest.TestCase):
    def make_bridge(self):
        bridge = MagicMock()
        bridge.get_lock_token.return_value = "FREE"

        calls = {"count": 0}

        def rows():
            calls["count"] += 1
            if calls["count"] <= 2:
                return [ROW.copy()]
            return []

        bridge.get_active_queue_rows.side_effect = rows
        return bridge

    @patch.object(dispatcher, "send_alert")
    @patch.object(dispatcher, "process_task")
    @patch.object(dispatcher, "WorkerCoordinator")
    @patch.object(dispatcher, "TaskResultLogger")
    @patch.object(dispatcher, "ConfirmGate")
    @patch.object(dispatcher, "OutputValidator")
    @patch.object(dispatcher, "TaskExecutor")
    @patch.object(dispatcher, "TaskRouterBridge")
    @patch.object(dispatcher, "SelfHealingBridge")
    def test_normal_dispatch_claims_and_releases_worker(
        self, healing_cls, bridge_cls, executor_cls, validator_cls,
        gate_cls, logger_cls, coordinator_cls, process_task, send_alert
    ):
        healing_cls.return_value.preflight.return_value = (
            True, {"missing_required": [], "missing_keys": []}
        )

        bridge = self.make_bridge()
        bridge_cls.return_value = bridge

        logger_cls.return_value.stats.return_value = {
            "total_tasks": 1, "success": 1, "failed": 0
        }

        worker = MagicMock()
        worker.worker_id = "Claude-1"
        coordinator = coordinator_cls.return_value
        coordinator.assign_locked.return_value = worker

        process_task.return_value = (True, {"provider": "fake"})

        dispatcher._run_dispatcher()

        coordinator.assign_locked.assert_called_once_with(
            "TASK-PHASE5", "03_Bot/bot.py"
        )
        process_task.assert_called_once()
        coordinator.complete_locked.assert_called_once_with(
            "TASK-PHASE5",
            evidence="dispatcher SUCCESS",
            review=True,
        )

    @patch.object(dispatcher, "send_alert")
    @patch.object(dispatcher, "process_task")
    @patch.object(dispatcher, "WorkerCoordinator")
    @patch.object(dispatcher, "TaskResultLogger")
    @patch.object(dispatcher, "ConfirmGate")
    @patch.object(dispatcher, "OutputValidator")
    @patch.object(dispatcher, "TaskExecutor")
    @patch.object(dispatcher, "TaskRouterBridge")
    @patch.object(dispatcher, "SelfHealingBridge")
    def test_completion_failure_releases_stale_claim(
        self, healing_cls, bridge_cls, executor_cls, validator_cls,
        gate_cls, logger_cls, coordinator_cls, process_task, send_alert
    ):
        healing_cls.return_value.preflight.return_value = (
            True, {"missing_required": [], "missing_keys": []}
        )

        bridge = self.make_bridge()
        bridge_cls.return_value = bridge

        logger_cls.return_value.stats.return_value = {
            "total_tasks": 1, "success": 1, "failed": 0
        }

        worker = MagicMock()
        worker.worker_id = "Claude-1"

        coordinator = coordinator_cls.return_value
        coordinator.assign_locked.return_value = worker
        coordinator.complete_locked.side_effect = (
            dispatcher.CoordinationError("synthetic completion failure")
        )

        process_task.return_value = (True, {"provider": "fake"})

        dispatcher._run_dispatcher()

        process_task.assert_called_once()
        coordinator.release_locked.assert_called_once_with("TASK-PHASE5")

        send_alert.assert_called_once()
        self.assertEqual(
            send_alert.call_args.kwargs["stage"],
            "coordination-cleanup",
        )


    @patch.object(dispatcher, "send_alert")
    @patch.object(dispatcher, "process_task")
    @patch.object(dispatcher, "WorkerCoordinator")
    @patch.object(dispatcher, "TaskResultLogger")
    @patch.object(dispatcher, "ConfirmGate")
    @patch.object(dispatcher, "OutputValidator")
    @patch.object(dispatcher, "TaskExecutor")
    @patch.object(dispatcher, "TaskRouterBridge")
    @patch.object(dispatcher, "SelfHealingBridge")
    def test_coordination_conflict_blocks_before_execution(
        self, healing_cls, bridge_cls, executor_cls, validator_cls,
        gate_cls, logger_cls, coordinator_cls, process_task, send_alert
    ):
        healing_cls.return_value.preflight.return_value = (
            True, {"missing_required": [], "missing_keys": []}
        )

        bridge = self.make_bridge()
        bridge_cls.return_value = bridge

        logger_cls.return_value.stats.return_value = {
            "total_tasks": 0, "success": 0, "failed": 0
        }

        coordinator_cls.return_value.assign_locked.side_effect = (
            dispatcher.CoordinationError("module conflict")
        )

        dispatcher._run_dispatcher()

        process_task.assert_not_called()
        coordinator_cls.return_value.complete_locked.assert_not_called()

        bridge.move_queue_row.assert_called_once_with(
            ROW["raw_line"],
            "BLOCKED",
            section="Failed / Blocked",
            provider=ROW["assigned"],
        )

        send_alert.assert_called_once()
        self.assertEqual(
            send_alert.call_args.kwargs["stage"],
            "coordination",
        )


if __name__ == "__main__":
    unittest.main()
