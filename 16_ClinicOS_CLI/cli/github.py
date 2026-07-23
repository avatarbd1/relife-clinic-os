"""
github.py — Git status/add/commit/push wrapper
relife sync              -> add + commit + push (ডিফল্ট মেসেজ সহ)
relife sync "msg"        -> কাস্টম কমিট মেসেজ
relife sync status        -> শুধু git status দেখাবে
relife sync pull          -> git pull
"""

import subprocess
import shutil
from datetime import datetime
import config


def _run(cmd):
    return subprocess.run(cmd, cwd=config.ROOT, capture_output=True, text=True)


def check_git_available():
    if shutil.which("git") is None:
        print("❌ git ইনস্টল করা নেই। (pkg install git)")
        return False
    if not (config.ROOT / ".git").exists():
        print("⚠️  এই ফোল্ডারে এখনো git init করা হয়নি। প্রথমে 'git init' করুন।")
        return False
    return True


def status():
    if not check_git_available():
        return
    result = _run(["git", "status"])
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


def pull():
    if not check_git_available():
        return
    result = _run(["git", "pull"])
    print(result.stdout or result.stderr)
    config.log_activity("git_pull", result.stdout[:200])


def sync(message: str = None):
    if not check_git_available():
        return False

    message = message or f"Auto commit - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    add = _run(["git", "add", "."])
    if add.returncode != 0:
        print("❌ git add ব্যর্থ:", add.stderr)
        return False

    commit = _run(["git", "commit", "-m", message])
    print(commit.stdout or commit.stderr)
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr):
        print("❌ git commit ব্যর্থ।")
        return False

    push = _run(["git", "push"])
    print(push.stdout or push.stderr)
    if push.returncode != 0:
        print("❌ git push ব্যর্থ। রিমোট/অথেনটিকেশন চেক করুন।")
        config.append_json_log(config.ERROR_LOG, {"action": "git_push", "stderr": push.stderr[:1000]})
        return False

    print("✅ GitHub sync সম্পন্ন হয়েছে (add + commit + push)।")
    config.log_activity("git_sync", message)
    return True
