"""
run.py — Code Runner (Python / Bash / NodeJS)
relife run <file>          -> এক্সটেনশন দেখে অটো ডিটেক্ট করে চালাবে
relife run <file> --lang python|bash|node
আউটপুট workspace/outputs/ এ সেভ হবে, এরর হলে error_log.json এ যাবে।
"""

import subprocess
import shutil
from datetime import datetime
from pathlib import Path
import config

LANG_MAP = {
    ".py": ("python3", "python"),
    ".sh": ("bash", "bash"),
    ".js": ("node", "node"),
}


def detect_lang(filepath: str):
    ext = Path(filepath).suffix
    return LANG_MAP.get(ext)


def run_file(filepath: str, lang: str = None):
    config.ensure_dirs()
    path = Path(filepath)
    if not path.exists():
        print(f"❌ ফাইল পাওয়া যায়নি: {filepath}")
        return None

    if lang:
        interpreter = {"python": "python3", "bash": "bash", "node": "node"}.get(lang)
    else:
        detected = detect_lang(filepath)
        if not detected:
            print("❌ ভাষা শনাক্ত করা যায়নি। --lang python|bash|node ব্যবহার করুন।")
            return None
        interpreter, lang = detected

    if shutil.which(interpreter) is None:
        print(f"❌ '{interpreter}' ইনস্টল করা নেই। (relife doctor চালিয়ে চেক করুন)")
        return None

    print(f"▶️  Running {path.name} with {interpreter} ...\n")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    result = subprocess.run(
        [interpreter, str(path)],
        capture_output=True, text=True
    )

    stdout, stderr = result.stdout, result.stderr
    print(stdout)
    if stderr:
        print("--- STDERR ---")
        print(stderr)

    out_file = config.WORKSPACE / "outputs" / f"{path.stem}_{timestamp}.log"
    out_file.write_text(f"CMD: {interpreter} {path}\n\nSTDOUT:\n{stdout}\n\nSTDERR:\n{stderr}", encoding="utf-8")

    status = "Success" if result.returncode == 0 else "Error"
    config.append_json_log(config.RUN_LOG, {
        "file": path.name, "lang": lang, "status": status,
        "output_file": str(out_file),
    })

    if status == "Error":
        config.append_json_log(config.ERROR_LOG, {
            "file": path.name, "lang": lang, "stderr": stderr[:2000],
        })
        print(f"\n❌ Error লগ হয়েছে।")
    else:
        print(f"\n✅ সফলভাবে রান হয়েছে। আউটপুট: {out_file}")

    config.log_activity("code_run", f"{path.name} -> {status}")
    return result.returncode
