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
from pathlib import Path
import config


def find_git_root():
    """config.ROOT থেকে উপরের দিকে খুঁজে সবচেয়ে কাছের .git ফোল্ডার বের করে।
    এটা করা হয় কারণ CLI অন্য কোনো git repo এর সাবফোল্ডারে বসানো থাকতে পারে
    (যেমন 16_ClinicOS_CLI/ বৃহত্তর relife-clinic-os রিপোর ভেতরে)।
    """
    current = config.ROOT
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def check_git_available():
    if shutil.which("git") is None:
        print("❌ git ইনস্টল করা নেই। (pkg install git)")
        return None
    git_root = find_git_root()
    if git_root is None:
        print("⚠️  কোনো parent ফোল্ডারেও git init করা পাওয়া যায়নি। প্রথমে 'git init' করুন।")
        return None
    return git_root


def status():
    git_root = check_git_available()
    if not git_root:
        return
    result = _run(["git", "status"], cwd=git_root)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)


def pull():
    git_root = check_git_available()
    if not git_root:
        return
    result = _run(["git", "pull"], cwd=git_root)
    print(result.stdout or result.stderr)
    config.log_activity("git_pull", result.stdout[:200])


def sync(message: str = None):
    git_root = check_git_available()
    if not git_root:
        return False

    message = message or f"Auto commit - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    print(f"📁 Git root: {git_root}")

    add = _run(["git", "add", "."], cwd=git_root)
    if add.returncode != 0:
        print("❌ git add ব্যর্থ:", add.stderr)
        return False

    commit = _run(["git", "commit", "-m", message], cwd=git_root)
    print(commit.stdout or commit.stderr)
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr):
        print("❌ git commit ব্যর্থ।")
        return False

    push = _run(["git", "push"], cwd=git_root)
    print(push.stdout or push.stderr)
    if push.returncode != 0:
        print("❌ git push ব্যর্থ। রিমোট/অথেনটিকেশন চেক করুন।")
        config.append_json_log(config.ERROR_LOG, {"action": "git_push", "stderr": push.stderr[:1000]})
        return False

    print("✅ GitHub sync সম্পন্ন হয়েছে (add + commit + push)।")
    config.log_activity("git_sync", message)
    return True
