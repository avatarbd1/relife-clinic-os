#!/data/data/com.termux/files/usr/bin/bash
set -u

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$REPO_ROOT/15_AI_Brain/Logs"
mkdir -p "$LOG_DIR"
cd "$REPO_ROOT" || exit 1

PYTHON_BIN="${PREFIX:-/data/data/com.termux/files/usr}/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="$(command -v python3)" || exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] cron cycle start"

detector_status=0
"$PYTHON_BIN" 15_AI_Brain/Control/task_detector.py || detector_status=$?

scheduler_status=0
"$PYTHON_BIN" 15_AI_Brain/Control/scheduler.py --once || scheduler_status=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] cron cycle end detector=$detector_status scheduler=$scheduler_status"

if [ "$scheduler_status" -ne 0 ]; then
    exit "$scheduler_status"
fi
exit "$detector_status"
