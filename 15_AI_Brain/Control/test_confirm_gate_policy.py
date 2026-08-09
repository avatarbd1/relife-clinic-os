#!/usr/bin/env python3
"""Safety-policy tests for BrainOS Confirm Gate."""

import os
import tempfile
import unittest

from confirm_gate import ConfirmGate


class ConfirmGatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gate = ConfirmGate(repo_root=self.tmp.name)

    def test_outputs_are_low_risk(self):
        decision = self.gate.classify_target("15_AI_Brain/Outputs/TASK-TEST.md")
        self.assertEqual(decision["decision"], "AUTO_APPLY")

    def test_production_bot_is_never_auto_applied(self):
        decision = self.gate.classify_target("03_Bot/bot.py")
        self.assertEqual(decision["decision"], "BLOCKED_PRODUCTION")

    def test_control_source_requires_manual_review(self):
        decision = self.gate.classify_target("15_AI_Brain/Control/scheduler.py")
        self.assertEqual(decision["decision"], "MANUAL_REVIEW")

    def test_safe_apply_writes_only_output_path(self):
        result = self.gate.safe_auto_apply(
            "TASK-TEST",
            "15_AI_Brain/Outputs/TASK-TEST.md",
            "health check ok\n",
        )
        self.assertTrue(result["applied"])
        target = os.path.join(self.tmp.name, "15_AI_Brain", "Outputs", "TASK-TEST.md")
        with open(target, "r", encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "health check ok\n")

    def test_safe_apply_refuses_production(self):
        result = self.gate.safe_auto_apply("TASK-BLOCK", "03_Bot/bot.py", "unsafe")
        self.assertFalse(result["applied"])
        self.assertEqual(result["decision"], "BLOCKED_PRODUCTION")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "03_Bot", "bot.py")))

    def test_path_traversal_cannot_disguise_production_write(self):
        decision = self.gate.classify_target("15_AI_Brain/Outputs/../../03_Bot/bot.py")
        self.assertEqual(decision["decision"], "BLOCKED_PRODUCTION")

    def test_safe_apply_refuses_path_traversal_into_production(self):
        result = self.gate.safe_auto_apply(
            "TASK-ESCAPE",
            "15_AI_Brain/Outputs/../../03_Bot/bot.py",
            "unsafe",
        )
        self.assertFalse(result["applied"])
        self.assertEqual(result["decision"], "BLOCKED_PRODUCTION")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "03_Bot", "bot.py")))

    def test_absolute_or_repo_escaping_path_is_blocked(self):
        decision = self.gate.classify_target("../outside_repo.py")
        self.assertEqual(decision["decision"], "BLOCKED_PATH_ESCAPE")
        result = self.gate.safe_auto_apply("TASK-OUTSIDE", "../outside_repo.py", "unsafe")
        self.assertFalse(result["applied"])

    def test_unrecognized_path_fails_closed_to_manual_review(self):
        decision = self.gate.classify_target("some_new_top_level_dir/file.py")
        self.assertEqual(decision["decision"], "MANUAL_REVIEW")
        result = self.gate.safe_auto_apply("TASK-UNKNOWN", "some_new_top_level_dir/file.py", "unsafe")
        self.assertFalse(result["applied"])


if __name__ == "__main__":
    unittest.main()
