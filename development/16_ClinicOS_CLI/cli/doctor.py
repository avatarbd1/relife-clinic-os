"""
doctor.py — Environment health check
relife doctor -> python3, git, node, bash আছে কিনা, ফোল্ডার/DB ঠিক আছে কিনা চেক করে
"""

import shutil
import sys
import config


def check_tool(name, cmd):
    path = shutil.which(cmd)
    status = "✅ পাওয়া গেছে" if path else "❌ নেই"
    print(f"{name:<12}: {status}" + (f" ({path})" if path else ""))
    return bool(path)


def run():
    print("\n=== RELIFE DOCTOR — সিস্টেম চেক ===\n")
    print(f"Python       : ✅ {sys.version.split()[0]}")
    check_tool("Git", "git")
    check_tool("Bash", "bash")
    check_tool("Node.js", "node")

    print("\n--- ফোল্ডার চেক ---")
    config.ensure_dirs()
    for d in [config.WORKSPACE, config.LOGS_DIR, config.DATABASE_DIR, config.BACKUP_DIR, config.CONFIG_DIR]:
        print(f"{d.name:<15}: {'✅ ঠিক আছে' if d.exists() else '❌ মিসিং'}")

    print("\n--- সেটিংস ---")
    settings = config.load_settings()
    for k, v in settings.items():
        print(f"{k:<15}: {v}")

    print("\n✅ Doctor check সম্পন্ন।\n")
