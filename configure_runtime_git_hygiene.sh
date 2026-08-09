#!/data/data/com.termux/files/usr/bin/bash
set -eu

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT" || exit 1

RUNTIME_TRACKED_FILES=(
    "12_Handover/HANDOVER.md"
    "13_AI_Tasks/TASK_QUEUE.md"
    "15_AI_Brain/Monitor/DASHBOARD.md"
    "15_AI_Brain/Monitor/PHASE2_PROGRESS.md"
    "15_BrainOS/BRAIN_MEMORY.md"
    "15_BrainOS/BRAIN_QUEUE.md"
    "15_BrainOS/BRAIN_STATE.md"
    "15_BrainOS/TASK_DESCRIPTIONS.json"
)

git config core.fileMode false

mode="apply"
if [ "${1:-}" = "--restore-tracking" ]; then
    mode="restore"
fi

updated=0
for path in "${RUNTIME_TRACKED_FILES[@]}"; do
    if git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
        if [ "$mode" = "restore" ]; then
            git update-index --no-skip-worktree -- "$path"
        else
            git update-index --skip-worktree -- "$path"
        fi
        updated=$((updated + 1))
    fi
done

if [ "$mode" = "restore" ]; then
    echo "Restored normal Git tracking for $updated runtime state files."
else
    echo "Configured local Git hygiene for $updated runtime state files."
    echo "Runtime data was preserved; no files were deleted or reset."
fi
