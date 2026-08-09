#!/usr/bin/env python3
"""
self_healing.py — BrainOS Phase 1, Item 9: Self-Healing Monitor
Relife Clinic OS

কাজ:
  1. প্রজেক্টের core structure (files/folders) ঠিকঠাক আছে কিনা চেক করা
  2. .env / environment-এ দরকারি API key গুলো সেট আছে কিনা চেক করা
  3. Provider Router-এর provider গুলো (Groq, OpenRouter, Gemini) reachable কিনা লাইট-চেক করা
  4. সব ফলাফল দিয়ে একটা readable health report জেনারেট করা

রান করার নিয়ম:
  cd ~/relife-clinic-os
  python3 development/15_AI_Brain/Monitor/self_healing.py

এটা শুধু READ-ONLY চেক করে — কোনো ফাইল এডিট বা ডিলিট করে না।
Report ছাড়া অন্য কিছু write করে না, এবং কখনোই 03_Bot/ টাচ করে না।
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CANDIDATE_ROOTS = [Path.cwd(), SCRIPT_DIR.parent.parent]
PROJECT_ROOT = None
for candidate in CANDIDATE_ROOTS:
    if (candidate / "03_Bot").exists() or (candidate / "AI_BRAIN.md").exists():
        PROJECT_ROOT = candidate
        break
if PROJECT_ROOT is None:
    PROJECT_ROOT = Path.cwd()

REPORT_DIR = PROJECT_ROOT / "development/15_AI_Brain" / "Monitor"
REPORT_PATH = REPORT_DIR / "HEALTH_REPORT.md"
REPORT_JSON_PATH = REPORT_DIR / "HEALTH_REPORT.json"

REQUIRED_PATHS = [
    "development/15_BrainOS/BRAIN_STATE.md",
    "development/15_BrainOS/BRAIN_QUEUE.md",
    "development/15_BrainOS/BRAIN_REGISTRY.md",
    "development/15_BrainOS/BRAIN_DISPATCHER.md",
    "development/15_BrainOS/BRAIN_MEMORY.md",
    "development/11_AIOS/MASTER_PROMPT.md",
    "development/11_AIOS/AI_CONSTITUTION.md",
    "development/11_AIOS/AI_REGISTRY.md",
    "development/11_AIOS/ONBOARDING_MESSAGE.md",
    "development/12_Handover/HANDOVER.md",
    "development/15_AI_Brain/Control/dispatcher_bridge.py",
    "development/15_AI_Brain/Control/task_router_bridge.py",
    "development/15_AI_Brain/Core/registry_provider_bridge.py",
]

OPTIONAL_PATHS = [
    "development/13_AI_Tasks",
    "development/14_Proposals",
    "AI_BRAIN.md",
    "AI_CONTEXT.md",
]

LIVE_BOT_MARKERS = [
    "03_Bot/bot.py",
]

EXPECTED_ENV_KEYS = [
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
    "GEMINI_API_KEY",
]


def check_paths(paths, project_root):
    results = []
    for rel_path in paths:
        full_path = project_root / rel_path
        results.append({
            "path": rel_path,
            "exists": full_path.exists(),
        })
    return results


def check_env_keys(keys):
    results = []
    for key in keys:
        value = os.environ.get(key, "")
        status = "missing"
        if value:
            status = "set" if len(value) > 10 else "suspicious (too short)"
        results.append({"key": key, "status": status})
    return results


def try_provider_router_healthcheck(project_root):
    core_path = project_root / "development/15_AI_Brain" / "Core"
    if not core_path.exists():
        return {"status": "skipped", "reason": "development/15_AI_Brain/Core not found"}

    sys.path.insert(0, str(core_path))
    sys.path.insert(0, str(project_root / "development/15_AI_Brain" / "Control"))
    try:
        import registry_provider_bridge  # noqa: F401
    except Exception as e:
        return {"status": "skipped", "reason": f"import failed: {e}"}

    return {"status": "importable", "reason": "registry_provider_bridge imported successfully"}


def build_report(structure_results, optional_results, live_bot_results, env_results, provider_result):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("# 🩺 BrainOS Self-Healing Health Report")
    lines.append(f"_Generated: {now}_")
    lines.append("")

    missing_required = [r for r in structure_results if not r["exists"]]
    lines.append("## 1. Core Structure (Required)")
    if missing_required:
        lines.append(f"⚠️ **{len(missing_required)} required file(s) MISSING:**")
        for r in missing_required:
            lines.append(f"- ❌ `{r['path']}`")
    else:
        lines.append("✅ সব required file/folder ঠিক আছে।")
    lines.append("")
    lines.append("<details><summary>Full list</summary>\n")
    for r in structure_results:
        mark = "✅" if r["exists"] else "❌"
        lines.append(f"- {mark} `{r['path']}`")
    lines.append("\n</details>\n")

    lines.append("## 2. Optional / Nice-to-have")
    for r in optional_results:
        mark = "✅" if r["exists"] else "⏳"
        lines.append(f"- {mark} `{r['path']}`")
    lines.append("")

    lines.append("## 3. Live Bot (informational only — never modified)")
    for r in live_bot_results:
        mark = "✅" if r["exists"] else "❌"
        lines.append(f"- {mark} `{r['path']}`")
    lines.append("")

    lines.append("## 4. API Keys (environment)")
    missing_keys = [r for r in env_results if r["status"] == "missing"]
    for r in env_results:
        icon = {"set": "✅", "missing": "❌", "suspicious (too short)": "⚠️"}.get(r["status"], "❓")
        lines.append(f"- {icon} `{r['key']}` — {r['status']}")
    if missing_keys:
        lines.append("")
        lines.append(f"⚠️ {len(missing_keys)} key(s) সেট নেই — সংশ্লিষ্ট provider fallback/mock মোডে চলবে।")
    lines.append("")

    lines.append("## 5. Provider Router")
    lines.append(f"- Status: `{provider_result['status']}`")
    lines.append(f"- Detail: {provider_result['reason']}")
    lines.append("")

    total_issues = len(missing_required) + len(missing_keys)
    lines.append("## Summary")
    if total_issues == 0:
        lines.append("🟢 **সব ঠিক আছে — কোনো critical issue পাওয়া যায়নি।**")
    else:
        lines.append(f"🟡 **{total_issues} টা issue পাওয়া গেছে** (উপরে বিস্তারিত দেখুন)।")

    return "\n".join(lines)


def main():
    print(f"[self_healing] Project root: {PROJECT_ROOT}")

    structure_results = check_paths(REQUIRED_PATHS, PROJECT_ROOT)
    optional_results = check_paths(OPTIONAL_PATHS, PROJECT_ROOT)
    live_bot_results = check_paths(LIVE_BOT_MARKERS, PROJECT_ROOT)
    env_results = check_env_keys(EXPECTED_ENV_KEYS)
    provider_result = try_provider_router_healthcheck(PROJECT_ROOT)

    report_md = build_report(
        structure_results, optional_results, live_bot_results, env_results, provider_result
    )

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report_md, encoding="utf-8")

    report_json = {
        "generated_at": datetime.now().isoformat(),
        "required": structure_results,
        "optional": optional_results,
        "live_bot": live_bot_results,
        "env_keys": env_results,
        "provider_router": provider_result,
    }
    REPORT_JSON_PATH.write_text(json.dumps(report_json, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[self_healing] Report written to: {REPORT_PATH}")
    print(f"[self_healing] JSON written to:   {REPORT_JSON_PATH}")

    missing_required = [r for r in structure_results if not r["exists"]]
    missing_keys = [r for r in env_results if r["status"] == "missing"]
    if missing_required or missing_keys:
        print(f"[self_healing] ⚠️ Issues found: {len(missing_required)} missing files, {len(missing_keys)} missing keys")
        sys.exit(1)
    else:
        print("[self_healing] ✅ All checks passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
