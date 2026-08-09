#!/data/data/com.termux/files/usr/bin/bash
set -eu

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$REPO_ROOT/15_AI_Brain/Logs"
MARKER="# BrainOS managed cron cycle"
BASH_BIN="$(command -v bash)"
CRON_LINE="*/10 * * * * $BASH_BIN $REPO_ROOT/brainos_cron_cycle.sh >> $LOG_DIR/cron-cycle.log 2>&1"
TMP_DIR="${PREFIX:-/data/data/com.termux/files/usr}/tmp"
TMP_FILE="$TMP_DIR/brainos-cron.$$"

mkdir -p "$LOG_DIR" "$TMP_DIR"
bash "$REPO_ROOT/configure_runtime_git_hygiene.sh"

if ! command -v crontab >/dev/null 2>&1 || ! command -v crond >/dev/null 2>&1; then
    echo "cronie is not installed. Run: pkg install cronie -y"
    exit 2
fi

# Replace the managed entry instead of appending duplicates.
(crontab -l 2>/dev/null || true) \
    | awk -v marker="$MARKER" 'index($0, marker) == 0' > "$TMP_FILE"
{
    echo "$MARKER"
    echo "$CRON_LINE"
} >> "$TMP_FILE"
crontab "$TMP_FILE"
rm -f "$TMP_FILE"

# Stop only the legacy daemon recorded by this repository.
PID_FILE="$LOG_DIR/scheduler.pid"
if [ -f "$PID_FILE" ]; then
    scheduler_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [ -n "$scheduler_pid" ] && kill -0 "$scheduler_pid" 2>/dev/null; then
        cmdline="$(tr '\0' ' ' < "/proc/$scheduler_pid/cmdline" 2>/dev/null || true)"
        case "$cmdline" in
            *"15_AI_Brain/Control/scheduler.py"*)
                kill "$scheduler_pid"
                echo "Stopped legacy scheduler PID $scheduler_pid"
                ;;
        esac
    fi
    rm -f "$PID_FILE"
fi

if ! pgrep -x crond >/dev/null 2>&1; then
    crond
fi

echo "BrainOS cron installed:"
crontab -l | grep -A 1 -F "$MARKER"
