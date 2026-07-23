"""
task.py — Task Manager (SQLite backed)
relife task        -> নতুন টাস্ক তৈরি
relife task list    -> সব টাস্ক দেখা
relife task done ID -> টাস্ক সম্পন্ন করা
relife task search Q -> টাস্ক খোঁজা
"""

import sqlite3
from datetime import datetime
import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project TEXT,
    module TEXT,
    priority TEXT,
    description TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT,
    completed_at TEXT
);
"""


def get_conn():
    config.ensure_dirs()
    conn = sqlite3.connect(config.TASKS_DB)
    conn.execute(SCHEMA)
    conn.commit()
    return conn


def new_task_interactive():
    print("\n--- নতুন টাস্ক ---")
    project = input("Project : ").strip() or config.get_setting("current_project", "Relife Clinic")
    module = input("Module : ").strip()
    priority = input("Priority (High/Medium/Low) : ").strip() or "Medium"
    description = input("Description : ").strip()

    task_id = add_task(project, module, priority, description)
    print(f"\n✅ Task #{task_id} সেভ হয়েছে।\n")
    return task_id


def add_task(project, module, priority, description):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute(
        "INSERT INTO tasks (project, module, priority, description, status, created_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?)",
        (project, module, priority, description, now),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    config.append_json_log(config.TASK_LOG, {
        "task_id": task_id, "project": project, "module": module,
        "priority": priority, "description": description, "action": "created"
    })
    config.log_activity("task_created", f"#{task_id} {module}")
    return task_id


def list_tasks(status=None):
    conn = get_conn()
    cur = conn.cursor()
    if status:
        cur.execute("SELECT id, project, module, priority, status, created_at FROM tasks WHERE status=? ORDER BY id DESC", (status,))
    else:
        cur.execute("SELECT id, project, module, priority, status, created_at FROM tasks ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("কোনো টাস্ক পাওয়া যায়নি।")
        return []

    print(f"\n{'ID':<4}{'Project':<16}{'Module':<16}{'Priority':<10}{'Status':<10}")
    print("-" * 60)
    for r in rows:
        print(f"{r[0]:<4}{r[1][:15]:<16}{r[2][:15]:<16}{r[3]:<10}{r[4]:<10}")
    print()
    return rows


def complete_task(task_id):
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now().isoformat()
    cur.execute("UPDATE tasks SET status='completed', completed_at=? WHERE id=?", (now, task_id))
    conn.commit()
    changed = cur.rowcount
    conn.close()
    if changed:
        print(f"✅ Task #{task_id} সম্পন্ন হিসেবে চিহ্নিত হলো।")
        config.log_activity("task_completed", f"#{task_id}")
    else:
        print(f"⚠️ Task #{task_id} পাওয়া যায়নি।")
    return changed


def search_tasks(keyword):
    conn = get_conn()
    cur = conn.cursor()
    like = f"%{keyword}%"
    cur.execute(
        "SELECT id, project, module, priority, status FROM tasks "
        "WHERE description LIKE ? OR module LIKE ? OR project LIKE ? ORDER BY id DESC",
        (like, like, like),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print("কোনো মিল পাওয়া যায়নি।")
    else:
        print(f"\n{'ID':<4}{'Project':<16}{'Module':<16}{'Priority':<10}{'Status':<10}")
        print("-" * 60)
        for r in rows:
            print(f"{r[0]:<4}{r[1][:15]:<16}{r[2][:15]:<16}{r[3]:<10}{r[4]:<10}")
    return rows


def stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tasks")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'")
    completed = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status='pending'")
    pending = cur.fetchone()[0]
    conn.close()
    percent = round((completed / total) * 100, 1) if total else 0
    return {"total": total, "completed": completed, "pending": pending, "percent": percent}
