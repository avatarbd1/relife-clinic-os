import ast
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BOT_PATH = ROOT / "03_Bot" / "bot.py"
ASYNC_PATH = ROOT / "03_Bot" / "async_runtime.py"
OBS_PATH = ROOT / "03_Bot" / "observability.py"
BOT_SOURCE = BOT_PATH.read_text(encoding="utf-8")
ASYNC_SOURCE = ASYNC_PATH.read_text(encoding="utf-8")
OBS_SOURCE = OBS_PATH.read_text(encoding="utf-8")


def load_observability():
    spec = importlib.util.spec_from_file_location("observability_test", OBS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SentryPolicyTests(unittest.TestCase):
    def test_missing_dsn_does_not_initialize_or_crash(self):
        module = load_observability()
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(module.init_sentry())

    def test_init_disables_pii_locals_breadcrumbs_and_tracing(self):
        tree = ast.parse(OBS_SOURCE)
        init_call = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "init"
        )
        kwargs = {kw.arg: kw.value for kw in init_call.keywords}
        self.assertIs(kwargs["send_default_pii"].value, False)
        self.assertIs(kwargs["include_local_variables"].value, False)
        self.assertEqual(kwargs["max_breadcrumbs"].value, 0)
        self.assertEqual(kwargs["traces_sample_rate"].value, 0.0)

    def test_before_send_removes_context_and_redacts_phone(self):
        module = load_observability()
        event = {
            "request": {"data": "patient text"},
            "user": {"id": "123"},
            "breadcrumbs": {"values": []},
            "extra": {"update": "raw"},
            "exception": {"values": [{"value": "failed for 01712345678"}]},
        }
        cleaned = module._before_send(event, {})
        for field in ("request", "user", "breadcrumbs", "extra"):
            self.assertNotIn(field, cleaned)
        self.assertNotIn("01712345678", str(cleaned))

    def test_raw_telegram_content_is_never_attached(self):
        capture_calls = []
        for source in (BOT_SOURCE, ASYNC_SOURCE, OBS_SOURCE):
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.Call):
                    continue
                name = ""
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name in {"capture_exception", "capture_message", "set_context", "set_extra"}:
                    capture_calls.append(ast.unparse(node))

        self.assertTrue(capture_calls)
        forbidden = ("update.to_dict()", "update.message.text", "patient", "staff")
        for call in capture_calls:
            for phrase in forbidden:
                with self.subTest(call=call, phrase=phrase):
                    self.assertNotIn(phrase, call)

    def test_global_and_background_errors_are_captured(self):
        self.assertIn("capture_exception(context.error)", BOT_SOURCE)
        self.assertGreaterEqual(ASYNC_SOURCE.count("capture_exception(error)"), 2)

    def test_health_server_failure_is_captured_and_reraised(self):
        main = next(
            node for node in ast.parse(BOT_SOURCE).body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        self.assertTrue(any(isinstance(node, ast.Raise) for node in ast.walk(main)))
        self.assertIn("capture_exception(error)", ast.unparse(main))

    def test_both_requirements_files_include_sentry(self):
        for path in (ROOT / "requirements.txt", ROOT / "03_Bot" / "requirements.txt"):
            with self.subTest(path=path):
                self.assertIn("sentry-sdk", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
