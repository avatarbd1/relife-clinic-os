#!/usr/bin/env bash
#
# git_sync.sh — Relife Clinic OS এর জন্য এক-কমান্ডে Add + Commit + Push
# যেকোনো AI session বা owner নিজে এটা ব্যবহার করতে পারবে।
#
# ব্যবহার:
#   ./git_sync.sh "commit message here"
#
# যদি কোনো message না দেওয়া হয়, একটা auto timestamp-based message বসবে।

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

LOG_DIR="development/15_AI_Brain/Logs"
LOG_FILE="$LOG_DIR/GIT_SYNC_LOG.md"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

if [ -z "$1" ]; then
  COMMIT_MSG="Auto-sync: $TIMESTAMP"
else
  COMMIT_MSG="$1"
fi

echo "============================================================"
echo "🔄 GIT SYNC — Relife Clinic OS"
echo "============================================================"
echo ""
echo "📋 Current status:"
git status --short

CHANGES=$(git status --porcelain)

if [ -z "$CHANGES" ]; then
  echo ""
  echo "✅ কোনো change নেই — sync করার কিছু নেই।"
  {
    echo ""
    echo "## $TIMESTAMP"
    echo "- Status: NO CHANGES (nothing to sync)"
  } >> "$LOG_FILE"
  exit 0
fi

echo ""
echo "📦 Staging all changes..."
git add -A

echo ""
echo "📝 Committing: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

echo ""
echo "🚀 Pushing to origin/main..."
git push

COMMIT_HASH=$(git rev-parse --short HEAD)

echo ""
echo "✅ SYNC COMPLETE — commit $COMMIT_HASH pushed"

{
  echo ""
  echo "## $TIMESTAMP"
  echo "- Commit: \`$COMMIT_HASH\`"
  echo "- Message: $COMMIT_MSG"
  echo "- Files changed:"
  echo '```'
  echo "$CHANGES"
  echo '```'
} >> "$LOG_FILE"

echo ""
echo "📄 Log updated: $LOG_FILE"
