#!/usr/bin/env python3
"""Safety-policy tests for BrainOS Confirm Gate."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from confirm_gate import ConfirmGate


class ConfirmGatePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.gate = ConfirmGate(repo_root=self.tmp.name)

    # ---------- classification ----------

    def test_outputs_are_low_risk(self):
        decision = self.gate.classify_target("15_AI_Brain/Outputs/TASK-TEST.md")
        self.assertEqual(decision["decision"], "AUTO_APPLY")

    def test_production_bot_is_never_auto_applied(self):
        decision = self.gate.classify_target("03_Bot/bot.py")
        self.assertEqual(decision["decision"], "BLOCKED_PRODUCTION")

    def test_control_source_requires_manual_review(self):
        decision = self.gate.classify_target("15_AI_Brain/Control/scheduler.py")
        self.assertEqual(decision["decision"], "MANUAL_REVIEW")

    def test_unrecognized_path_fails_closed_to_manual_review(self):
        decision = self.gate.classify_target("some_new_top_level_dir/file.py")
        self.assertEqual(decision["decision"], "MANUAL_REVIEW")
        result = self.gate.safe_auto_apply("TASK-UNKNOWN", "some_new_top_level_dir/file.py", "unsafe")
        self.assertFalse(result["applied"])

    def test_path_traversal_cannot_disguise_production_write(self):
        decision = self.gate.classify_target("15_AI_Brain/Outputs/../../03_Bot/bot.py")
        self.assertEqual(decision["decision"], "BLOCKED_PRODUCTION")

    def test_absolute_path_is_blocked(self):
        decision = self.gate.classify_target("/etc/passwd")
        self.assertEqual(decision["decision"], "BLOCKED_PATH_ESCAPE")
        result = self.gate.safe_auto_apply("TASK-ABS", "/etc/passwd", "unsafe")
        self.assertFalse(result["applied"])
        self.assertFalse(os.path.exists("/tmp/__confirm_gate_should_not_exist__"))

    def test_absolute_or_repo_escaping_path_is_blocked(self):
        decision = self.gate.classify_target("../outside_repo.py")
        self.assertEqual(decision["decision"], "BLOCKED_PATH_ESCAPE")
        result = self.gate.safe_auto_apply("TASK-OUTSIDE", "../outside_repo.py", "unsafe")
        self.assertFalse(result["applied"])

    # ---------- safe_auto_apply write behaviour ----------

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

    def test_safe_apply_refuses_path_traversal_into_production(self):
        result = self.gate.safe_auto_apply(
            "TASK-ESCAPE",
            "15_AI_Brain/Outputs/../../03_Bot/bot.py",
            "unsafe",
        )
        self.assertFalse(result["applied"])
        self.assertEqual(result["decision"], "BLOCKED_PRODUCTION")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "03_Bot", "bot.py")))

    # ---------- symlink / filesystem-level containment ----------

    def test_symlink_escape_is_blocked_even_though_prefix_matches(self):
        """15_AI_Brain/Outputs/ is replaced with a symlink pointing at a
        directory outside the repo. The string prefix check in
        classify_target() would allow this (it starts with the right
        prefix); only the filesystem-level resolve+containment check in
        _resolve_and_contain() can catch it."""
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)

        brain_dir = Path(self.tmp.name) / "15_AI_Brain"
        brain_dir.mkdir(parents=True, exist_ok=True)
        outputs_link = brain_dir / "Outputs"
        if outputs_link.exists():
            outputs_link.rmdir()
        outputs_link.symlink_to(outside.name, target_is_directory=True)

        result = self.gate.safe_auto_apply(
            "TASK-SYMLINK-ESCAPE",
            "15_AI_Brain/Outputs/escape.md",
            "should not land outside the repo",
        )
        self.assertFalse(result["applied"])
        self.assertEqual(result["decision"], "BLOCKED_SYMLINK_ESCAPE")
        self.assertFalse((Path(outside.name) / "escape.md").exists())

    # ---------- approve() re-validates instead of trusting stored flags ----------

    def test_approve_rejects_tampered_proposal_pointed_at_production(self):
        """A proposal is created for a safe target, then the Pending JSON
        on disk is edited (simulating tampering or a stale/incorrect
        stored flag) so target_path now points at 03_Bot/ while the
        stored 'blocked'/'safe_auto' flags are left saying it's safe.
        approve() must re-classify target_path fresh and refuse the
        write — it must not trust the stored flags."""
        pending_path = self.gate.proposals_dir / "Pending" / "TASK-TAMPER.proposal.json"
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        tampered_proposal = {
            "task_id": "TASK-TAMPER",
            "target_path": "03_Bot/malicious.py",
            "content": "unsafe content",
            "status": "PENDING",
            "decision": "AUTO_APPLY",  # lie: stored decision says safe
            "blocked": False,           # lie: stored flag says not blocked
            "safe_auto": True,          # lie: stored flag says safe to auto-apply
            "created_at": "2026-01-01T00:00:00",
        }
        pending_path.write_text(json.dumps(tampered_proposal), encoding="utf-8")

        result = self.gate.approve("TASK-TAMPER")
        self.assertEqual(result["status"], "MANUAL_REVIEW_REQUIRED")
        self.assertFalse(
            (Path(self.tmp.name) / "03_Bot" / "malicious.py").exists()
        )

    def test_automatic_approve_rejects_tampered_proposal(self):
        """Same tampering scenario, but through the automatic=True path
        that propose() uses internally for safe_auto proposals."""
        pending_path = self.gate.proposals_dir / "Pending" / "TASK-TAMPER-AUTO.proposal.json"
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        tampered_proposal = {
            "task_id": "TASK-TAMPER-AUTO",
            "target_path": "03_Bot/malicious.py",
            "content": "unsafe content",
            "status": "PENDING",
            "decision": "AUTO_APPLY",
            "blocked": False,
            "safe_auto": True,
            "created_at": "2026-01-01T00:00:00",
        }
        pending_path.write_text(json.dumps(tampered_proposal), encoding="utf-8")

        result = self.gate.approve("TASK-TAMPER-AUTO", automatic=True)
        self.assertEqual(result["status"], "MANUAL_REVIEW_REQUIRED")
        self.assertFalse(
            (Path(self.tmp.name) / "03_Bot" / "malicious.py").exists()
        )


if __name__ == "__main__":
    unittest.main()
