#!/usr/bin/env python3
"""
confirm_gate.py — BrainOS Confirm Gate
Relife Clinic OS

Policy: autonomous development, controlled production.
Generated artifacts under 15_AI_Brain/Outputs/ may auto-apply.
Production and all other paths remain behind explicit owner approval.
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
SAFE_AUTO_PREFIXES = ("15_AI_Brain/Outputs/",)
PROPOSALS_DIR = Path("15_AI_Brain/Proposals")
GATE_LOG = Path("15_AI_Brain/Logs/confirm_gate.log")

STATUS_SUBDIR = {
    "PENDING": "Pending",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
}


def _normalize(target_path: str) -> str:
    return target_path.replace("\\", "/").lstrip("./")


def _is_blocked(target_path: str) -> bool:
    return _normalize(target_path).startswith(BLOCKED_PREFIX)


def _is_safe_auto_target(target_path: str) -> bool:
    normalized = _normalize(target_path)
    return any(normalized.startswith(prefix) for prefix in SAFE_AUTO_PREFIXES)


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
        blocked = _is_blocked(target_path)
        safe_auto = _is_safe_auto_target(target_path) and not blocked
        proposal = {
            "task_id": task_id,
            "target_path": target_path,
            "content": content,
            "status": "PENDING",
            "blocked": blocked,
            "safe_auto": safe_auto,
            "created_at": datetime.now().isoformat(),
        }

        proposal_path = self._proposal_path(task_id, status="PENDING")
        proposal_path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
        _log({"action": "PROPOSE", "task_id": task_id, "target_path": target_path,
              "blocked": blocked, "safe_auto": safe_auto})

        if safe_auto:
            result = self.approve(task_id, automatic=True)
            return {**proposal, "status": result["status"], "auto_approved": True}

        proposal["auto_approved"] = False
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

    def approve(self, task_id: str, automatic: bool = False) -> Dict:
        proposal_path = self._proposal_path(task_id, status="PENDING")
        if not proposal_path.exists():
            return {"status": "ERROR", "error": f"No pending proposal found for {task_id}"}

        data = json.loads(proposal_path.read_text(encoding="utf-8"))

        if automatic and not data.get("safe_auto", False):
            _log({"action": "AUTO_APPROVE_DENIED", "task_id": task_id,
                  "target_path": data.get("target_path")})
            return {"status": "MANUAL_REVIEW_REQUIRED", "task_id": task_id,
                    "target_path": data.get("target_path")}

        if data.get("blocked"):
            result = {
                "status": "MANUAL_REVIEW_REQUIRED",
                "task_id": task_id,
                "target_path": data["target_path"],
                "message": (
                    f"'{data['target_path']}' is inside {BLOCKED_PREFIX}/; "
                    "automatic apply is forbidden. Owner review is required."
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
        data["approved_automatically"] = automatic

        new_path = self._proposal_path(task_id, status="APPROVED")
        new_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        proposal_path.unlink()

        _log({"action": "AUTO_APPROVE" if automatic else "APPROVE",
              "task_id": task_id, "target_path": data["target_path"]})
        return {"status": "APPLIED", "task_id": task_id,
                "target_path": data["target_path"], "automatic": automatic}

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
    for command in ("approve", "reject", "preview"):
        p = sub.add_parser(command)
        p.add_argument("task_id")

    args = parser.parse_args()
    gate = ConfirmGate()
    if args.command == "list":
        pending = gate.list_pending()
        if not pending:
            print("No pending proposals.")
        for p in pending:
            flag = "BLOCKED (03_Bot)" if p["blocked"] else "manual review"
            print(f"- {p['task_id']} -> {p['target_path']} [{flag}]")
    elif args.command == "approve":
        print(json.dumps(gate.approve(args.task_id), indent=2, ensure_ascii=False))
    elif args.command == "reject":
        print(json.dumps(gate.reject(args.task_id), indent=2, ensure_ascii=False))
    elif args.command == "preview":
        data = gate.preview(args.task_id)
        print(json.dumps(data, indent=2, ensure_ascii=False) if data else "Proposal not found.")
    else:
        parser.print_help()


def _self_test() -> None:
    gate = ConfirmGate()

    safe_id = "GATE-TEST-SAFE-AUTO"
    safe_target = "15_AI_Brain/Outputs/GATE-TEST-SAFE-AUTO.md"
    result = gate.propose(safe_id, "safe test", safe_target)
    assert result["status"] == "APPLIED"
    assert result["auto_approved"] is True
    assert Path(safe_target).exists()
    assert Path(f"15_AI_Brain/Proposals/Approved/{safe_id}.proposal.json").exists()

    blocked_id = "GATE-TEST-BLOCKED"
    blocked_target = "03_Bot/should_never_write.py"
    blocked = gate.propose(blocked_id, "blocked test", blocked_target)
    assert blocked["blocked"] is True
    assert blocked["auto_approved"] is False
    assert not Path(blocked_target).exists()
    assert gate.approve(blocked_id)["status"] == "MANUAL_REVIEW_REQUIRED"
    gate.reject(blocked_id)

    manual_id = "GATE-TEST-MANUAL"
    manual_target = "15_AI_Brain/Control/should_not_auto_write.py"
    manual = gate.propose(manual_id, "manual test", manual_target)
    assert manual["auto_approved"] is False
    assert not Path(manual_target).exists()
    gate.reject(manual_id)

    print("ALL CONFIRM GATE SELF-TESTS PASSED")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _cli()
    else:
        _self_test()
