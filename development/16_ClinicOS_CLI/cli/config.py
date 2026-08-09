"""
config.py — Central paths, settings loader/saver, project config
সব মডিউল এই ফাইল থেকে path ও settings নেবে।
"""

import json
import os
from pathlib import Path
from datetime import datetime

# ---------- Core Paths ----------
ROOT = Path(__file__).resolve().parent.parent          # Relife-Clinic-OS/
CLI_DIR = ROOT / "cli"
WORKSPACE = ROOT / "workspace"
LOGS_DIR = ROOT / "logs"
DATABASE_DIR = ROOT / "database"
BACKUP_DIR = ROOT / "backup"
GITHUB_DIR = ROOT / "github"
CONFIG_DIR = ROOT / "config"

SETTINGS_FILE = DATABASE_DIR / "settings.json"
TASKS_DB = DATABASE_DIR / "tasks.db"
PROJECTS_DB = DATABASE_DIR / "projects.db"

TASK_LOG = LOGS_DIR / "task_log.json"
RUN_LOG = LOGS_DIR / "run_log.json"
ERROR_LOG = LOGS_DIR / "error_log.json"
ACTIVITY_LOG = LOGS_DIR / "activity_log.json"

DEFAULT_SETTINGS = {
    "current_project": "Relife Clinic",
    "editor": "nano",
    "auto_backup": True,
    "created_at": datetime.now().isoformat(),
    "theme": "default",
}


def ensure_dirs():
    """সব দরকারি ফোল্ডার/ফাইল নিশ্চিত করে (না থাকলে বানায়)"""
    for d in [WORKSPACE, WORKSPACE / "prompts", WORKSPACE / "generated_code",
              WORKSPACE / "outputs", WORKSPACE / "temp", WORKSPACE / "archive",
              LOGS_DIR, DATABASE_DIR, BACKUP_DIR, GITHUB_DIR, CONFIG_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)

    for log_file in [TASK_LOG, RUN_LOG, ERROR_LOG, ACTIVITY_LOG]:
        if not log_file.exists():
            log_file.write_text("[]", encoding="utf-8")


def load_settings():
    ensure_dirs()
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()


def save_settings(data: dict):
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_setting(key, default=None):
    return load_settings().get(key, default)


def set_setting(key, value):
    data = load_settings()
    data[key] = value
    save_settings(data)
    return data


def append_json_log(path: Path, entry: dict):
    """JSON array log ফাইলে নতুন এন্ট্রি যোগ করে"""
    ensure_dirs()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            data = []
    except (json.JSONDecodeError, FileNotFoundError):
        data = []
    entry["timestamp"] = datetime.now().isoformat()
    data.append(entry)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def read_json_log(path: Path):
    ensure_dirs()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def log_activity(action: str, detail: str = ""):
    append_json_log(ACTIVITY_LOG, {"action": action, "detail": detail})
