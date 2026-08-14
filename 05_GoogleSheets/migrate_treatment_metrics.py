#!/usr/bin/env python3
"""Stage 1 migration — 05_Treatments-এ structured clinical কলাম যোগ করে।

শুধু শেষে কলাম যোগ করে। কোনো কলাম সরায় না, নাম বদলায় না, ঘর মোছে না।
পুরোনো সারিগুলো ফাঁকা থাকবে — কোড Remarks থেকে fallback করে পড়বে।

    python migrate_treatment_metrics.py            # dry run (কিছুই বদলায় না)
    python migrate_treatment_metrics.py --apply    # সত্যিকারে যোগ করে

চালানোর আগে Sheet-এর ব্যাকআপ নাও।
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_Bot"))

import config  # noqa: E402
import sheets  # noqa: E402


NEW_COLUMNS = {
    config.SHEET_TREATMENTS: [
        ("Pain_Before", "সেশনের আগে ব্যথা (0-10)"),
        ("Pain_After", "সেশনের পরে ব্যথা (0-10)"),
        ("Response", "Better / Same / Worse"),
        ("Modification", "আজ প্ল্যান থেকে কী বদলানো হলো"),
    ],
    config.SHEET_APPOINTMENTS: [
        ("Received_By", "কে রোগী receive করেছে"),
        ("Gender", "booking-এর সময় patient gender snapshot"),
        ("Room", "automatic treatment-room reservation"),
        ("Bed", "automatic bed reservation"),
        ("Station", "Treatment অথবা Traction"),
    ],
}


def main(apply_changes: bool) -> int:
    print("=" * 60)
    print("Stage 1 migration — structured clinical কলাম")
    print("DRY RUN — কিছুই বদলানো হবে না" if not apply_changes else "⚠️  APPLY MODE")
    print("=" * 60)
    print()

    total_planned = 0
    for title, columns in NEW_COLUMNS.items():
        try:
            ws = sheets._worksheet(title)
            headers = ws.row_values(1)
        except Exception as error:
            print(f"❌ {title}: পড়া গেল না ({type(error).__name__}: {error})")
            return 1

        missing = [(name, note) for name, note in columns if name not in headers]
        print(f"{title} — বর্তমানে {len(headers)} কলাম")
        if not missing:
            print("   ✅ সব কলাম আগে থেকেই আছে\n")
            continue

        for name, note in missing:
            print(f"   ➕ {name:<14} — {note}")
        total_planned += len(missing)

        if apply_changes:
            start = len(headers) + 1
            needed = start + len(missing) - 1
            if ws.col_count < needed:
                ws.add_cols(needed - ws.col_count)
            for offset, (name, _note) in enumerate(missing):
                ws.update_cell(1, start + offset, name)
            sheets._invalidate_cache(ws)
            print(f"   ✅ {len(missing)} টি কলাম শেষে যোগ করা হলো")
        print()

    print("-" * 60)
    if not total_planned:
        print("করার কিছু নেই — সব কলাম আগে থেকেই আছে।")
    elif apply_changes:
        print(f"✅ মোট {total_planned} টি কলাম যোগ করা হলো।")
        print("পুরোনো সারিগুলো ফাঁকা — বটে সেটা স্বাভাবিক, Remarks fallback কাজ করবে।")
    else:
        print(f"{total_planned} টি কলাম যোগ হবে। সত্যিকারে চালাতে:")
        print("   python migrate_treatment_metrics.py --apply")
    print("-" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main("--apply" in sys.argv))
