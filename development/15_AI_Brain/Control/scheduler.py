#!/usr/bin/env python3
"""Run the BrainOS maintenance cycle every six hours or once for verification."""
import argparse
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

from alert_notifier import send_alert

INTERVAL = 6 * 3600  # 6 hours
REPO_ROOT = Path(__file__).resolve().parents[3]
LOG = REPO_ROOT / "development/15_AI_Brain" / "Logs" / "scheduler.log"

def run(args):
    r = subprocess.run(args, cwd=REPO_ROOT, capture_output=True, text=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {' '.join(args)}\n{r.stdout}\n{r.stderr}\n---\n")
    return r

def run_cycle() -> bool:
    commands = [
        [sys.executable, "development/15_AI_Brain/Control/dispatcher_bridge.py"],
        [sys.executable, "development/15_AI_Brain/Control/self_healing_bridge.py"],
        [sys.executable, "development/15_AI_Brain/Monitor/phase2_progress_tracker.py"],
        [sys.executable, "development/15_AI_Brain/Monitor/dashboard_generator.py"],
    ]
    ok = True
    for args in commands:
        result = run(args)
        if result.returncode != 0:
            ok = False
            print(f"FAILED ({result.returncode}): {' '.join(args)}", file=sys.stderr)
            send_alert(
                "Scheduled command failed",
                f"exit={result.returncode}; command={args[1] if len(args) > 1 else args[0]}",
                stage="scheduler",
            )
    return ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = parser.parse_args()
    print(f"Scheduler started. Interval: {INTERVAL}s. Log: {LOG}")
    if args.once:
        return 0 if run_cycle() else 1
    while True:
        run_cycle()
        print(f"[{datetime.now()}] Cycle done. Sleeping {INTERVAL}s...")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
