#!/usr/bin/env python3
"""Relife Clinic OS — কে আসলে ক্যাশ হ্যান্ডল করে, সেটা বের করে।

READ-ONLY। কোনো শীটে কিছু লেখে না, কোনো কলাম যোগ করে না।
Financial_Access backfill-এর proposed table ছাপে, যাতে অনুমান করতে না হয়।

চালাও:  cd ~/relife-clinic-os && python relife_cash_roster.py
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "03_Bot"))

try:
    import config
    import sheets
except Exception as error:  # pragma: no cover
    print(f"❌ bot module load করা গেল না: {type(error).__name__}: {error}")
    sys.exit(1)


# কোন শীটের কোন কলামে "কে করেছে" লেখা থাকে, আর সেটা কোন capability বোঝায়।
# operate = টাকা নাড়াচাড়া করে | read = শুধু দেখা/অনুমোদনের দরকার
ACTOR_COLUMNS = [
    (config.SHEET_PAYMENTS,      "Received_By",  "operate", "রোগীর পেমেন্ট নিয়েছে"),
    (config.SHEET_CASH_MOVEMENT, "Moved_By",     "operate", "হ্যান্ডওভার পাঠিয়েছে"),
    (config.SHEET_CASH_MOVEMENT, "Confirmed_By", "operate", "হ্যান্ডওভার গ্রহণ করেছে"),
    (config.SHEET_EXPENSES,      "Requested_By", "read",    "খরচের অনুরোধ করেছে"),
    (config.SHEET_EXPENSES,      "Approved_By",  "read",    "খরচ অনুমোদন করেছে"),
    (config.SHEET_EXPENSES,      "Paid_By",      "operate", "খরচের টাকা দিয়েছে"),
    (config.SHEET_SALARY,        "Paid_By",      "operate", "বেতন দিয়েছে"),
]


def load(title: str) -> list[dict]:
    try:
        return sheets.safe_get_all_records(sheets._worksheet(title))
    except Exception as error:
        print(f"⚠️  {title} পড়া গেল না ({type(error).__name__}) — বাদ দেওয়া হলো")
        return []


def main() -> int:
    staff_rows = load(config.SHEET_STAFF)
    if not staff_rows:
        print("❌ 08_Staff পড়া গেল না। থামছি।")
        return 1
    mapping_rows = load(config.SHEET_STAFF_DEPARTMENT_ACCESS)

    # নাম → Staff_ID (finance শীটগুলোতে নাম লেখা থাকে, ID না)
    id_by_name: dict[str, str] = {}
    duplicate_names: set[str] = set()
    for row in staff_rows:
        name = str(row.get("Full_Name", "")).strip().casefold()
        staff_id = str(row.get("Staff_ID", "")).strip()
        if not name or not staff_id:
            continue
        if name in id_by_name and id_by_name[name] != staff_id:
            duplicate_names.add(name)
        id_by_name[name] = staff_id

    name_by_id = {
        str(r.get("Staff_ID", "")).strip(): str(r.get("Full_Name", "")).strip()
        for r in staff_rows
    }
    status_by_id = {
        str(r.get("Staff_ID", "")).strip(): str(r.get("Status", "")).strip()
        for r in staff_rows
    }

    # assignments: staff_id → {(department, role)}
    assignments: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in mapping_rows:
        if str(row.get("Status", "Active")).strip().casefold() != "active":
            continue
        staff_id = str(row.get("Staff_ID", "")).strip()
        dept = str(row.get("Department", "")).strip()
        role = str(row.get("Role", "")).strip()
        if staff_id and dept and role:
            assignments[staff_id].add((dept, role))

    # প্রমাণ সংগ্রহ
    evidence: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    level: dict[str, str] = defaultdict(lambda: "none")
    unmatched: dict[str, int] = defaultdict(int)

    cache: dict[str, list[dict]] = {}
    for title, column, capability, label in ACTOR_COLUMNS:
        if title not in cache:
            cache[title] = load(title)
        for row in cache[title]:
            actor = str(row.get(column, "")).strip()
            if not actor:
                continue
            staff_id = id_by_name.get(actor.casefold())
            if not staff_id:
                unmatched[actor] += 1
                continue
            evidence[staff_id][label] += 1
            if capability == "operate":
                level[staff_id] = "Operate"
            elif level[staff_id] == "none":
                level[staff_id] = "Read"

    print("=" * 62)
    print("বাস্তবে কে ক্যাশ হ্যান্ডল করে — প্রমাণভিত্তিক")
    print("=" * 62)
    print()

    if not evidence:
        print("কোনো finance কার্যকলাপ পাওয়া যায়নি। শীটে ডেটা আছে কিনা দেখো।")
    for staff_id in sorted(evidence, key=lambda s: name_by_id.get(s, s)):
        name = name_by_id.get(staff_id, "??")
        roles_text = ", ".join(
            f"{d}/{r}" for d, r in sorted(assignments.get(staff_id, set()))
        ) or "কোনো active assignment নেই"
        flag = "" if status_by_id.get(staff_id, "").casefold() == "active" else "  ⚠️ 08_Staff-এ Active নয়"
        print(f"{staff_id}  {name}{flag}")
        print(f"   assignment : {roles_text}")
        print(f"   প্রস্তাব     : Financial_Access = {level[staff_id]}")
        for label, count in sorted(evidence[staff_id].items(), key=lambda kv: -kv[1]):
            print(f"      • {label}: {count} বার")
        print()

    print("-" * 62)
    print("যাদের কোনো finance কার্যকলাপ নেই → প্রস্তাব: None")
    print("-" * 62)
    idle = [
        sid for sid in sorted(assignments)
        if sid not in evidence and status_by_id.get(sid, "").casefold() == "active"
    ]
    for staff_id in idle:
        roles_text = ", ".join(
            f"{d}/{r}" for d, r in sorted(assignments[staff_id])
        )
        print(f"{staff_id}  {name_by_id.get(staff_id, '??'):<22} {roles_text}")
    if not idle:
        print("(কেউ নেই)")
    print()

    if duplicate_names:
        print("-" * 62)
        print("⚠️  08_Staff-এ একই নামে একাধিক Staff_ID")
        print("-" * 62)
        for name in sorted(duplicate_names):
            ids = [
                str(r.get("Staff_ID", "")).strip() for r in staff_rows
                if str(r.get("Full_Name", "")).strip().casefold() == name
            ]
            print(f"  {name}: {', '.join(ids)}")
        print("  → এদের finance ইতিহাস দুই ID-তে ভাগ হয়ে আছে।")
        print()

    if unmatched:
        print("-" * 62)
        print("⚠️  finance শীটে এমন নাম আছে যা 08_Staff-এ মেলেনি")
        print("-" * 62)
        for actor, count in sorted(unmatched.items(), key=lambda kv: -kv[1])[:15]:
            print(f"  {actor!r}: {count} বার")
        print("  → বানানে অমিল, নাকি বিদায়ী স্টাফ? Financial_Access দেওয়ার আগে মেলাও।")
        print()

    print("=" * 62)
    print("এটি প্রস্তাব মাত্র — অনুমোদন ছাড়া কোনো migration চালাবে না।")
    print("Owner-কে সবসময় Operate দিতে হবে, কার্যকলাপ থাকুক বা না থাকুক।")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
