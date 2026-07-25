#!/usr/bin/env python3
"""
SELF_HEALING_BRIDGE v1.0 — Connects self_healing.py to BrainOS dispatch loop
Phase 1 Step 9/10: Self-healing monitor (integration)

Extends 15_AI_Brain/Monitor/self_healing.py — does NOT recreate it.
self_healing.py already performs the actual read-only health checks
(core structure, env keys, provider importability) and writes
Monitor/HEALTH_REPORT.md + HEALTH_REPORT.json. This bridge just wires
that existing check into the dispatch loop as a pre-flight gate, the
same way task_router_bridge.py and registry_provider_bridge.py wire
TASK_ROUTER.py and provider_router.py into BrainOS.

Integration points:
- Reuses: 15_AI_Brain/Monitor/self_healing.py (check_paths, check_env_keys,
  try_provider_router_healthcheck, build_report)
- Writes to: BRAIN_MEMORY.md (log), BRAIN_STATE.md (last health-check status)
- Read by: dispatcher_bridge.py, before EXECUTE step
"""

import os
import sys
import json
from datetime import datetime

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
os.chdir(REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "15_AI_Brain", "Monitor"))

import self_healing  # reuse existing, already-working module

BRAIN_MEMORY_PATH = "15_BrainOS/BRAIN_MEMORY.md"
BRAIN_STATE_PATH = "15_BrainOS/BRAIN_STATE.md"


class SelfHealingBridge:
    """Bridge between self_healing.py and BrainOS file system."""

    def __init__(self):
        self.project_root = self_healing.PROJECT_ROOT

    def run_check(self):
        """Run the existing self-healing checks and return a summary dict.
        Does not exit the process (unlike self_healing.main()) so it is
        safe to call from inside the dispatcher loop."""
        structure_results = self_healing.check_paths(self_healing.REQUIRED_PATHS, self.project_root)
        optional_results = self_healing.check_paths(self_healing.OPTIONAL_PATHS, self.project_root)
        live_bot_results = self_healing.check_paths(self_healing.LIVE_BOT_MARKERS, self.project_root)
        env_results = self_healing.check_env_keys(self_healing.EXPECTED_ENV_KEYS)
        provider_result = self_healing.try_provider_router_healthcheck(self.project_root)

        report_md = self_healing.build_report(
            structure_results, optional_results, live_bot_results, env_results, provider_result
        )

        report_dir = self_healing.REPORT_DIR
        report_dir.mkdir(parents=True, exist_ok=True)
        self_healing.REPORT_PATH.write_text(report_md, encoding="utf-8")
        self_healing.REPORT_JSON_PATH.write_text(
            json.dumps({
                "generated_at": datetime.now().isoformat(),
                "required": structure_results,
                "optional": optional_results,
                "live_bot": live_bot_results,
                "env_keys": env_results,
                "provider_router": provider_result,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        missing_required = [r for r in structure_results if not r["exists"]]
        missing_keys = [r for r in env_results if r["status"] == "missing"]
        healthy = not missing_required and not missing_keys

        return {
            "healthy": healthy,
            "missing_required": [r["path"] for r in missing_required],
            "missing_keys": [r["key"] for r in missing_keys],
            "provider_router": provider_result,
        }

    def log_to_memory(self, result):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = "INFO" if result["healthy"] else "WARN"
        status = "PASS" if result["healthy"] else "ISSUES_FOUND"
        line = f"[{ts}] [{level}] [SELF_HEALING] Pre-flight check: {status}"
        if not result["healthy"]:
            if result["missing_required"]:
                line += f" — missing: {', '.join(result['missing_required'])}"
            if result["missing_keys"]:
                line += f" — missing keys: {', '.join(result['missing_keys'])}"
        with open(BRAIN_MEMORY_PATH, "a") as f:
            f.write(line + "\n")

    def update_brain_state(self, result):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "HEALTHY" if result["healthy"] else "ISSUES_FOUND"
        block = (
            "\n## Self-Healing Monitor\n"
            f"- Last Check: {ts}\n"
            f"- Status: {status}\n"
            f"- Report: 15_AI_Brain/Monitor/HEALTH_REPORT.md\n"
        )
        with open(BRAIN_STATE_PATH, "r") as f:
            content = f.read()

        if "## Self-Healing Monitor" in content:
            before, rest = content.split("## Self-Healing Monitor", 1)
            after_parts = rest.split("##", 1)
            after = "##" + after_parts[1] if len(after_parts) > 1 else ""
            content = before + block.lstrip("\n") + ("\n" + after if after else "")
        else:
            content += block

        with open(BRAIN_STATE_PATH, "w") as f:
            f.write(content)

    def preflight(self):
        """Convenience entry point for dispatcher_bridge.py:
        run check, log it, update state, return True/False (safe to proceed)."""
        result = self.run_check()
        self.log_to_memory(result)
        self.update_brain_state(result)
        return result["healthy"], result


if __name__ == "__main__":
    bridge = SelfHealingBridge()
    print("=" * 50)
    print("SELF-HEALING BRIDGE — Step 9/10")
    print("=" * 50)
    healthy, result = bridge.preflight()
    if healthy:
        print("✅ System healthy — safe to dispatch.")
    else:
        print("⚠️ Issues found:")
        for p in result["missing_required"]:
            print(f"   ❌ missing: {p}")
        for k in result["missing_keys"]:
            print(f"   ❌ missing key: {k}")
    print(f"\nFull report: 15_AI_Brain/Monitor/HEALTH_REPORT.md")
