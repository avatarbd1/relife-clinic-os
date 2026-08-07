#!/usr/bin/env python3
"""
confirm_gate.py — BrainOS Phase 2, Item 2: Dry-Run + Confirm Gate
Relife Clinic OS
(Reorganized: Pending / Approved / Rejected lifecycle folders)
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = os.path.expanduser("~/relife-clinic-os")
if os.path.isdir(REPO_ROOT):
    os.chdir(REPO_ROOT)

BLOCKED_PREFIX = "03_Bot"
PROPOSALS_DIR = Path("15_AI_Brain/Proposals")
GATE_LOG = Path("15_AI_Brain/Logs/confirm_gate.log")

STATUS_SUBDIR = {
    "PENDING": "Pending",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
}


def _is_blocked(target_path: str) -> bool:
    return target_path.replace("\\", "/").lstrip("./").startswith(BLOCKED_PREFIX)


def _log(entry: Dict):
    GATE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now().isoformat(), **entry}
    with open(GATE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class ConfirmGate:
    def __init__(self):
        for sub in STATUS_SUBDIR.values():
            (PROPOSALS_DIR / sub).mkdir(parents=True, exist_ok=True)

    def _proposal_path(self, task_id: str, status: str = None) -> Path:
        if status:
            return PROPOSALS_DIR / STATUS_SUBDIR[status] / f"{task_id}.proposal.json"
        for sub in ("Pending", "Approved", "Rejected"):
            p = PROPOSALS_DIR / sub / f"{task_id}.proposal.json"
            if p.exists():
                return p
        return PROPOSALS_DIR / STATUS_SUBDIR["PENDING"] / f"{task_id}.proposal.json"

    def propose(self, task_id: str, content: str, target_path: str) -> Dict:
        proposal = {
            "task_id": task_id,
            "target_path": target_path,
            "content": content,
            "status": "PENDING",
            "blocked": _is_blocked(target_path),
            "created_at": datetime.now().isoformat(),
        }

        proposal_path = self._proposal_path(task_id, status="PENDING")
        proposal_path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")

        _log({"action": "PROPOSE", "task_id": task_id, "target_path": target_path,
              "blocked": proposal["blocked"]})

        return proposal

    def list_pending(self) -> list:
        pending = []
        for f in (PROPOSALS_DIR / STATUS_SUBDIR["PENDING"]).glob("*.proposal.json"):
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("status") == "PENDING":
                pending.append(data)
        return pending

    def preview(self, task_id: str) -> Optional[Dict]:
        p = self._proposal_path(task_id)
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))

    def approve(self, task_id: str) -> Dict:
        proposal_path = self._proposal_path(task_id, status="PENDING")
        if not proposal_path.exists():
            return {"status": "ERROR", "error": f"No pending proposal found for {task_id}"}

        data = json.loads(proposal_path.read_text(encoding="utf-8"))

        if data.get("blocked"):
            result = {
                "status": "MANUAL_REVIEW_REQUIRED",
                "task_id": task_id,
                "target_path": data["target_path"],
                "message": (
                    f"'{data['target_path']}' হলো {BLOCKED_PREFIX}/ এর ভেতরে — "
                    "এটা কখনো script দিয়ে auto-apply হবে না। owner নিজে হাতে "
                    "review করে বসাতে হবে। Proposal এখনো Proposals/Pending/ ফোল্ডারে "
                    "সংরক্ষিত আছে, content দেখতে preview() ব্যবহার করুন।"
                ),
            }
            _log({"action": "APPROVE_BLOCKED", "task_id": task_id,
                  "target_path": data["target_path"]})
            return result

        target = Path(data["target_path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data["content"], encoding="utf-8")

        data["status"] = "APPROVED"
        data["approved_at"] = datetime.now().isoformat()

        new_path = self._proposal_path(task_id, status="APPROVED")
        new_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        proposal_path.unlink()

        _log({"action": "APPROVE", "task_id": task_id, "target_path": data["target_path"]})

        return {"status": "APPLIED", "task_id": task_id, "target_path": data["target_path"]}

    def reject(self, task_id: str) -> Dict:
        proposal_path = self._proposal_path(task_id, status="PENDING")
        if not proposal_path.exists():
            return {"status": "ERROR", "error": f"No pending proposal found for {task_id}"}

        data = json.loads(proposal_path.read_text(encoding="utf-8"))
        data["status"] = "REJECTED"
        data["rejected_at"] = datetime.now().isoformat()

        new_path = self._proposal_path(task_id, status="REJECTED")
        new_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        proposal_path.unlink()

        _log({"action": "REJECT", "task_id": task_id, "target_path": data["target_path"]})

        return {"status": "REJECTED", "task_id": task_id}


def _cli():
    parser = argparse.ArgumentParser(description="BrainOS Confirm Gate CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list")

    p_approve = sub.add_parser("approve")
    p_approve.add_argument("task_id")

    p_reject = sub.add_parser("reject")
    p_reject.add_argument("task_id")

    p_preview = sub.add_parser("preview")
    p_preview.add_argument("task_id")

    args = parser.parse_args()
    gate = ConfirmGate()

    if args.command == "list":
        pending = gate.list_pending()
        if not pending:
            print("কোনো pending proposal নেই।")
        for p in pending:
            flag = "🚫 BLOCKED (03_Bot)" if p["blocked"] else "✅ ready to approve"
            print(f"- {p['task_id']} → {p['target_path']} [{flag}]")

    elif args.command == "approve":
        result = gate.approve(args.task_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "reject":
        result = gate.reject(args.task_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.command == "preview":
        data = gate.preview(args.task_id)
        if data is None:
            print("Proposal পাওয়া যায়নি।")
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))

    else:
        parser.print_help()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _cli()
    else:
        print("=== Confirm Gate Self-Test ===\n")
        gate = ConfirmGate()

        p1 = gate.propose("GATE-TEST-NORMAL", "টেস্ট কনটেন্ট — এটা approve হওয়া উচিত।",
                           "15_AI_Brain/Outputs/GATE-TEST-NORMAL.md")
        print(f"Proposed (normal): blocked={p1['blocked']}")

        p2 = gate.propose("GATE-TEST-BLOCKED", "এটা 03_Bot এ যাওয়ার কথা — ব্লক হওয়া উচিত।",
                           "03_Bot/should_never_write.py")
        print(f"Proposed (03_Bot): blocked={p2['blocked']}")

        print("\nPending proposals:")
        for p in gate.list_pending():
            print(f"  - {p['task_id']} ({'BLOCKED' if p['blocked'] else 'ok'})")

        r1 = gate.approve("GATE-TEST-NORMAL")
        print(f"\nApprove normal → {r1['status']}")
        assert r1["status"] == "APPLIED"
        assert Path("15_AI_Brain/Outputs/GATE-TEST-NORMAL.md").exists()
        assert Path("15_AI_Brain/Proposals/Approved/GATE-TEST-NORMAL.proposal.json").exists()
        assert not Path("15_AI_Brain/Proposals/Pending/GATE-TEST-NORMAL.proposal.json").exists()

        r2 = gate.approve("GATE-TEST-BLOCKED")
        print(f"Approve 03_Bot target → {r2['status']}")
        assert r2["status"] == "MANUAL_REVIEW_REQUIRED"
        assert not Path("03_Bot/should_never_write.py").exists()
        assert Path("15_AI_Brain/Proposals/Pending/GATE-TEST-BLOCKED.proposal.json").exists()

        gate.reject("GATE-TEST-BLOCKED")
        assert Path("15_AI_Brain/Proposals/Rejected/GATE-TEST-BLOCKED.proposal.json").exists()
        assert not Path("15_AI_Brain/Proposals/Pending/GATE-TEST-BLOCKED.proposal.json").exists()

        print("\n✅ ALL SELF-TESTS PASSED")
