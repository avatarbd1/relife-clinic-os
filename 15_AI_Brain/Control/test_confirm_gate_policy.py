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


if __name__ == "__main__":
    unittest.main()
