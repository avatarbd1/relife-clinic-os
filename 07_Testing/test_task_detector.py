import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock


ROOT = Path(__file__).resolve().parents[1]
CONTROL_DIR = ROOT / "15_AI_Brain" / "Control"
sys.path.insert(0, str(CONTROL_DIR))

MODULE_PATH = CONTROL_DIR / "task_detector.py"
SPEC = importlib.util.spec_from_file_location("task_detector_tests", MODULE_PATH)
detector = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = detector
SPEC.loader.exec_module(detector)


class TaskDetectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        detector.INBOX_DIR = root / "TaskInbox"
        detector.PROCESSING_DIR = detector.INBOX_DIR / "processing"
        detector.PROCESSED_DIR = detector.INBOX_DIR / "processed"
        detector.FAILED_DIR = detector.INBOX_DIR / "failed"
        detector.MEMORY_PATH = root / "BRAIN_MEMORY.md"
        detector.MAX_FILES_PER_SCAN = 10
        detector.MAX_FILE_BYTES = 64

        self.bridge = MagicMock()
        self.bridge.create_and_persist_task.return_value = {
            "status": "PROVIDER_ASSIGNED",
            "task_id": "TASK-TEST",
        }
        self.classify = MagicMock(return_value={
            "type": "Documentation",
            "description": "persisted description",
            "priority": "LOW",
            "target_file": "",
        })
        self.save = MagicMock()

    def tearDown(self):
        self.temp.cleanup()

    def write_inbox(self, name: str, content: str) -> Path:
        detector.INBOX_DIR.mkdir(parents=True, exist_ok=True)
        path = detector.INBOX_DIR / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_successful_file_is_claimed_once_and_archived(self):
        self.write_inbox("one.txt", "make a short report")

        first = detector.run_scan(self.bridge, self.classify, self.save)
        second = detector.run_scan(self.bridge, self.classify, self.save)

        self.assertEqual(first, (1, 0))
        self.assertEqual(second, (0, 0))
        self.bridge.create_and_persist_task.assert_called_once()
        self.save.assert_called_once_with(
            "TASK-TEST", "persisted description", "make a short report", ""
        )
        self.assertEqual(list(detector.INBOX_DIR.glob("*.txt")), [])
        self.assertEqual(len(list(detector.PROCESSED_DIR.iterdir())), 1)

    def test_oversized_file_fails_without_creating_task(self):
        self.write_inbox("large.txt", "x" * 65)

        result = detector.run_scan(self.bridge, self.classify, self.save)

        self.assertEqual(result, (0, 1))
        self.bridge.create_and_persist_task.assert_not_called()
        self.assertEqual(len(list(detector.FAILED_DIR.iterdir())), 1)

    def test_empty_file_fails_closed(self):
        self.write_inbox("empty.txt", "   ")

        result = detector.run_scan(self.bridge, self.classify, self.save)

        self.assertEqual(result, (0, 1))
        self.classify.assert_not_called()
        self.bridge.create_and_persist_task.assert_not_called()

    def test_scan_respects_batch_limit(self):
        detector.MAX_FILES_PER_SCAN = 1
        self.write_inbox("a.txt", "first")
        self.write_inbox("b.txt", "second")

        result = detector.run_scan(self.bridge, self.classify, self.save)

        self.assertEqual(result, (1, 0))
        self.assertEqual(len(list(detector.INBOX_DIR.glob("*.txt"))), 1)


if __name__ == "__main__":
    unittest.main()
