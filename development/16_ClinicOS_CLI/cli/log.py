"""
log.py — Log viewer
relife logs             -> আজকের run log দেখাবে
relife logs run          -> সব run log
relife logs error         -> সব error log
relife logs activity      -> সব activity log
relife logs search KEYWORD -> error log এ খোঁজা
"""

from datetime import datetime
import config


def _print_table(rows, columns):
    if not rows:
        print("কোনো এন্ট্রি পাওয়া যায়নি।\n")
        return
    widths = {c: max(len(c), *(len(str(r.get(c, ''))) for r in rows)) + 2 for c in columns}
    header = "".join(c.ljust(widths[c]) for c in columns)
    print(header)
    print("-" * len(header))
    for r in rows:
        print("".join(str(r.get(c, ''))[:widths[c]-2].ljust(widths[c]) for c in columns))
    print()


def show_today_runs():
    data = config.read_json_log(config.RUN_LOG)
    today = datetime.now().strftime("%Y-%m-%d")
    todays = [d for d in data if d.get("timestamp", "").startswith(today)]
    print(f"\n--- আজকের Run Log ({today}) ---")
    _print_table(todays, ["timestamp", "file", "lang", "status"])
    return todays


def show_run_log():
    data = config.read_json_log(config.RUN_LOG)
    print("\n--- সম্পূর্ণ Run Log ---")
    _print_table(data, ["timestamp", "file", "lang", "status"])
    return data


def show_error_log():
    data = config.read_json_log(config.ERROR_LOG)
    print("\n--- Error Log ---")
    _print_table(data, ["timestamp", "file", "lang"])
    return data


def show_activity_log():
    data = config.read_json_log(config.ACTIVITY_LOG)
    print("\n--- Activity Log ---")
    _print_table(data, ["timestamp", "action", "detail"])
    return data


def search_errors(keyword):
    data = config.read_json_log(config.ERROR_LOG)
    matches = [d for d in data if keyword.lower() in str(d).lower()]
    print(f"\n--- '{keyword}' এর জন্য {len(matches)}টি মিল ---")
    for m in matches:
        print(f"[{m.get('timestamp')}] {m.get('file')}: {m.get('stderr','')[:120]}")
    print()
    return matches
