#!/usr/bin/env python3
"""scheduler.py — Simple background loop: runs dispatcher_bridge + self_healing every N seconds."""
import time, subprocess, sys
from pathlib import Path
from datetime import datetime

INTERVAL = 6 * 3600  # 6 hours
LOG = Path.home() / "relife-clinic-os/15_AI_Brain/Logs/scheduler.log"

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    with open(LOG, "a") as f:
        f.write(f"[{datetime.now()}] {cmd}\n{r.stdout}\n{r.stderr}\n---\n")
    return r

if __name__ == "__main__":
    print(f"Scheduler started. Interval: {INTERVAL}s. Log: {LOG}")
    while True:
        run("python3 15_AI_Brain/Control/dispatcher_bridge.py")
        run("python3 15_AI_Brain/Control/self_healing_bridge.py")
        run("python3 15_AI_Brain/Monitor/phase2_tracker.py 2>/dev/null || true")
        print(f"[{datetime.now()}] Cycle done. Sleeping {INTERVAL}s...")
        time.sleep(INTERVAL)
