"""
backup.py — ZIP Backup ও Restore
relife backup           -> নতুন টাইমস্ট্যাম্পড ব্যাকআপ বানাবে
relife backup list       -> সব ব্যাকআপ দেখাবে
relife backup restore N  -> N নম্বর ব্যাকআপ থেকে রিস্টোর করবে
relife backup clean       -> পুরনো ব্যাকআপ (৭ দিনের বেশি) মুছে ফেলবে
"""

import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import config


def create_backup():
    config.ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project = config.get_setting("current_project", "project").replace(" ", "_")
    zip_name = f"{project}_backup_{timestamp}.zip"
    zip_path = config.BACKUP_DIR / zip_name

    # যা ব্যাকআপ হবে: cli, workspace, database, config, logs (backup ফোল্ডার বাদে)
    include = ["cli", "workspace", "database", "config", "logs", "github"]

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder in include:
            src = config.ROOT / folder
            if not src.exists():
                continue
            for file in src.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(config.ROOT))

    size_kb = round(zip_path.stat().st_size / 1024, 1)
    print(f"✅ ব্যাকআপ তৈরি হয়েছে: {zip_name} ({size_kb} KB)")
    config.set_setting("last_backup", datetime.now().isoformat())
    config.log_activity("backup_created", zip_name)
    return zip_path


def list_backups():
    config.ensure_dirs()
    backups = sorted(config.BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        print("কোনো ব্যাকআপ পাওয়া যায়নি।")
        return []
    print(f"\n{'#':<4}{'Name':<45}{'Size(KB)':<10}{'Date'}")
    print("-" * 90)
    for i, b in enumerate(backups, 1):
        size = round(b.stat().st_size / 1024, 1)
        date = datetime.fromtimestamp(b.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"{i:<4}{b.name:<45}{size:<10}{date}")
    print()
    return backups


def restore_backup(index: int):
    backups = list_backups()
    if not backups or index < 1 or index > len(backups):
        print("❌ ভুল ব্যাকআপ নম্বর।")
        return False
    zip_path = backups[index - 1]
    confirm = input(f"⚠️  '{zip_path.name}' থেকে রিস্টোর করলে বর্তমান ফাইল ওভাররাইট হবে। আগে যান? (yes/no): ")
    if confirm.strip().lower() != "yes":
        print("বাতিল করা হলো।")
        return False
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(config.ROOT)
    print(f"✅ রিস্টোর সম্পন্ন হয়েছে: {zip_path.name}")
    config.log_activity("backup_restored", zip_path.name)
    return True


def clean_old_backups(days: int = 7):
    config.ensure_dirs()
    cutoff = datetime.now() - timedelta(days=days)
    removed = 0
    for b in config.BACKUP_DIR.glob("*.zip"):
        if datetime.fromtimestamp(b.stat().st_mtime) < cutoff:
            b.unlink()
            removed += 1
    print(f"🧹 {removed}টি পুরনো ব্যাকআপ মুছে ফেলা হয়েছে (>{days} দিন)।")
    config.log_activity("backup_cleanup", f"removed={removed}")
    return removed
