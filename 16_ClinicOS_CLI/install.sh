#!/usr/bin/env bash
# install.sh — Relife CLI কে Termux/Linux এ গ্লোবাল কমান্ড হিসেবে সেটআপ করে
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_PATH="$PROJECT_DIR/cli/relife"

chmod +x "$CLI_PATH"

# Termux হলে ~/../usr/bin এ, নাহলে ~/.local/bin এ লিংক করি
if [ -d "$PREFIX/bin" ]; then
    TARGET_BIN="$PREFIX/bin"
else
    TARGET_BIN="$HOME/.local/bin"
    mkdir -p "$TARGET_BIN"
fi

ln -sf "$CLI_PATH" "$TARGET_BIN/relife"

echo ""
echo "✅ ইনস্টল সম্পন্ন হয়েছে।"
echo "   এখন যেকোনো জায়গা থেকে শুধু লিখুন:  relife"
echo ""
echo "   (যদি 'command not found' দেখায়, তাহলে টার্মিনাল বন্ধ করে আবার খুলুন,"
echo "    অথবা 'export PATH=\$PATH:$TARGET_BIN' চালান।)"
echo ""
