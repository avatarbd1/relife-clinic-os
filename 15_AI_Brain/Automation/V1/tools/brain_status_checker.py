from pathlib import Path

task_file = Path("13_AI_Tasks/TASK_QUEUE.md")

if not task_file.exists():
    print("TASK_QUEUE not found")
    exit()

data = task_file.read_text(encoding="utf-8")

pending = data.count("Pending")
progress = data.count("In-Progress")
done = data.count("Done")

print("=== AI BRAIN STATUS REPORT ===")
print(f"Pending: {pending}")
print(f"In-Progress: {progress}")
print(f"Done: {done}")

print("Health: OK")
