import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOT_PATH = ROOT / "03_Bot" / "bot.py"
TREE = ast.parse(BOT_PATH.read_text(encoding="utf-8"))


def function_node(name):
    return next(
        node for node in TREE.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )


class BackgroundAiPolicyTests(unittest.TestCase):
    def test_long_ai_handlers_schedule_background_work(self):
        for name in ("staffai_receive", "clinicalai_receive"):
            node = function_node(name)
            scheduled = [
                call for call in ast.walk(node)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "create_task"
            ]
            with self.subTest(handler=name):
                self.assertEqual(len(scheduled), 1)

    def test_global_concurrent_updates_remains_disabled(self):
        source = BOT_PATH.read_text(encoding="utf-8")
        self.assertNotIn(".concurrent_updates(", source)


if __name__ == "__main__":
    unittest.main()
