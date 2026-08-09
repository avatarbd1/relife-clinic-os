import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
CONTROL_DIR = ROOT / "15_AI_Brain" / "Control"
CORE_DIR = ROOT / "15_AI_Brain" / "Core"
LOGS_DIR = ROOT / "15_AI_Brain" / "Logs"
sys.path.insert(0, str(CONTROL_DIR))
sys.path.insert(0, str(CORE_DIR))
sys.path.insert(0, str(LOGS_DIR))
MODULE_PATH = CONTROL_DIR / "dispatcher_bridge.py"

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
    "description": "Use the persisted task description",
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


    def test_process_task_keeps_output_in_memory_until_validation_and_gate(self):
        bridge = MagicMock()
        bridge.router.provider_router.route.return_value = {
            "status": "SUCCESS",
            "selected_provider": "groq",
            "fallback_used": False,
            "retry_count": 0,
        }
        bridge.set_queue_row_status.return_value = ROW["raw_line"]

        executor = MagicMock()
        executor.execute.return_value = {
            "status": "SUCCESS",
            "task_id": ROW["task_id"],
            "provider": "groq",
            "output": "# Valid output",
            "attempts": 1,
        }
        validator = MagicMock()
        validator.validate.return_value = {"valid": True, "errors": []}
        gate = MagicMock()
        gate.propose.return_value = {"status": "APPLIED", "auto_approved": True}
        logger = MagicMock()

        ok, _ = dispatcher.process_task(
            bridge, executor, validator, gate, logger, ROW.copy()
        )

        self.assertTrue(ok)
        prompt = executor.execute.call_args.kwargs["prompt"]
        self.assertIn(ROW["description"], prompt)
        self.assertFalse(executor.execute.call_args.kwargs["persist_output"])
        gate.propose.assert_called_once_with(
            task_id=ROW["task_id"],
            content="# Valid output",
            target_path="15_AI_Brain/Outputs/TASK-PHASE5.py",
        )

    def test_queue_rows_load_persisted_description_and_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            brainos = root / "15_BrainOS"
            brainos.mkdir()
            queue = brainos / "BRAIN_QUEUE.md"
            queue.write_text(
                "# Queue\n## Active Queue\n"
                "| TASK_ID | Type | Priority | Status | Assigned | Created |\n"
                "|---|---|---|---|---|---|\n"
                "| TASK-META | Documentation | NORMAL | QUEUED | groq | now |\n"
                "\n## Completed\n",
                encoding="utf-8",
            )
            (brainos / "TASK_DESCRIPTIONS.json").write_text(
                '{"TASK-META":{"description":"real requested report",'
                '"target_file":"03_Bot/bot.py"}}',
                encoding="utf-8",
            )
            router_bridge = dispatcher.TaskRouterBridge.__new__(
                dispatcher.TaskRouterBridge
            )
            router_bridge.brain_queue_path = str(queue)

            with patch("task_router_bridge.REPO_ROOT", str(root)):
                rows = router_bridge.get_active_queue_rows()

        self.assertEqual(rows[0]["description"], "real requested report")
        self.assertEqual(rows[0]["target_file"], "03_Bot/bot.py")


if __name__ == "__main__":
    unittest.main()
