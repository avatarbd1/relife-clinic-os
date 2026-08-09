#!/usr/bin/env python3
"""
confirm_gate.py — BrainOS Confirm Gate
Relife Clinic OS

Policy: autonomous development, controlled production.

Risk classification (see classify_target):
  AUTO_APPLY           -> 15_AI_Brain/Outputs/**  (safe generated artifacts)
  BLOCKED_PRODUCTION   -> 03_Bot/**                (never auto-applied, ever)
  MANUAL_REVIEW        -> 15_AI_Brain/Control/** (BrainOS's own control/source
                           code) and any other/unrecognized path — fails
                           closed rather than auto-applying.
  BLOCKED_PATH_ESCAPE  -> paths that try to leave the repo root via ".." or
                           an absolute path. Always denied.

Path tricks (e.g. "15_AI_Brain/Outputs/../../03_Bot/x") are resolved with
posixpath.normpath BEFORE any decision is made, so they cannot disguise a
production write as a safe one.
"""

import os
import sys
import json
import argparse
import posixpath
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

DEFAULT_REPO_ROOT = os.path.expanduser("~/relife-clinic-os")

BLOCKED_PREFIX = "03_Bot"
CONTROL_PREFIX = "15_AI_Brain/Control"
SAFE_AUTO_PREFIXES = ("15_AI_Brain/Outputs/",)

STATUS_SUBDIR = {
    "PENDING": "Pending",
    "APPROVED": "Approved",
    "REJECTED": "Rejected",
}

DECISION_AUTO_APPLY = "AUTO_APPLY"
DECISION_BLOCKED_PRODUCTION = "BLOCKED_PRODUCTION"
DECISION_MANUAL_REVIEW = "MANUAL_REVIEW"
DECISION_BLOCKED_PATH_ESCAPE = "BLOCKED_PATH_ESCAPE"


def _normalize(target_path: str) -> str:
    """Resolve '..'/'.' segments so path tricks resolve to their real
    destination before any safety decision is made."""
    cleaned = (target_path or "").replace("\\", "/").strip()
    normalized = posixpath.normpath(cleaned)
    if normalized == ".":
        return ""
    return normalized


def _escapes_repo_root(normalized_path: str) -> bool:
    return normalized_path.startswith("..") or normalized_path.startswith("/")


class ConfirmGate:
    def __init__(self, repo_root: Optional[str] = None):
        base = repo_root or (DEFAULT_REPO_ROOT if os.path.isdir(DEFAULT_REPO_ROOT) else os.getcwd())
        self.repo_root = Path(base)
        self.proposals_dir = self.repo_root / "15_AI_Brain" / "Proposals"
        self.gate_log = self.repo_root / "15_AI_Brain" / "Logs" / "confirm_gate.log"
        for sub in STATUS_SUBDIR.values():
            (self.proposals_dir / sub).mkdir(parents=True, exist_ok=True)

    # ---------- risk classification ----------

    def classify_target(self, target_path: str) -> Dict:
        normalized = _normalize(target_path)

        # D. Path traversal / absolute-path tricks must not bypass anything.
        if _escapes_repo_root(normalized):
            return {"decision": DECISION_BLOCKED_PATH_ESCAPE, "normalized_path": normalized}

        # B. 03_Bot/ can NEVER be automatically modified.
        if normalized == BLOCKED_PREFIX or normalized.startswith(BLOCKED_PREFIX + "/"):
            return {"decision": DECISION_BLOCKED_PRODUCTION, "normalized_path": normalized}

        # C. BrainOS's own control/source code requires manual review.
        if normalized == CONTROL_PREFIX or normalized.startswith(CONTROL_PREFIX + "/"):
            return {"decision": DECISION_MANUAL_REVIEW, "normalized_path": normalized}

        # A. Only explicitly-approved safe output paths may auto-apply.
        if any(normalized.startswith(prefix) for prefix in SAFE_AUTO_PREFIXES):
            return {"decision": DECISION_AUTO_APPLY, "normalized_path": normalized}

        # E. Anything unrecognized fails closed to manual review.
        return {"decision": DECISION_MANUAL_REVIEW, "normalized_path": normalized}

    def _log(self, entry: Dict):
        self.gate_log.parent.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": datetime.now().isoformat(), **entry}
        with open(self.gate_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def safe_auto_apply(self, task_id: str, target_path: str, content: str) -> Dict:
        """Apply content directly ONLY when classification is AUTO_APPLY.
        Anything else is refused and logged — fail closed."""
        decision = self.classify_target(target_path)

        if decision["decision"] != DECISION_AUTO_APPLY:
            self._log({
                "action": "SAFE_AUTO_APPLY_DENIED",
                "task_id": task_id,
                "target_path": target_path,
                "decision": decision["decision"],
            })
            return {"applied": False, "task_id": task_id, "target_path": target_path,
                    "decision": decision["decision"]}

        target = self.repo_root / decision["normalized_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        self._log({
            "action": "SAFE_AUTO_APPLY",
            "task_id": task_id,
            "target_path": decision["normalized_path"],
        })
        return {"applied": True, "task_id": task_id, "target_path": decision["normalized_path"],
                "decision": decision["decision"]}

    # ---------- proposal lifecycle (propose / approve / reject / preview) ----------

    def _proposal_path(self, task_id: str, status: str = None) -> Path:
        if status:
            return self.proposals_dir / STATUS_SUBDIR[status] / f"{task_id}.proposal.json"
        for sub in ("Pending", "Approved", "Rejected"):
            p = self.proposals_dir / sub / f"{task_id}.proposal.json"
            if p.exists():
                return p
        return self.proposals_dir / STATUS_SUBDIR["PENDING"] / f"{task_id}.proposal.json"

    def propose(self, task_id: str, content: str, target_path: str) -> Dict:
        decision = self.classify_target(target_path)
        blocked = decision["decision"] in (DECISION_BLOCKED_PRODUCTION, DECISION_BLOCKED_PATH_ESCAPE)
        safe_auto = decision["decision"] == DECISION_AUTO_APPLY

        proposal = {
            "task_id": task_id,
            "target_path": target_path,
            "content": content,
            "status": "PENDING",
            "decision": decision["decision"],
            "blocked": blocked,
            "safe_auto": safe_auto,
            "created_at": datetime.now().isoformat(),
        }

        proposal_path = self._proposal_path(task_id, status="PENDING")
        proposal_path.write_text(json.dumps(proposal, indent=2, ensure_ascii=False), encoding="utf-8")
        self._log({"action": "PROPOSE", "task_id": task_id, "target_path": target_path,
                    "decision": decision["decision"]})

        if safe_auto:
            result = self.approve(task_id, automatic=True)
            return {**proposal, "status": result["status"], "auto_approved": True}

        proposal["auto_approved"] = False
        return proposal

    def list_pending(self) -> list:
        pending = []
        for f in (self.proposals_dir / STATUS_SUBDIR["PENDING"]).glob("*.proposal.json"):
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
            self._log({"action": "AUTO_APPROVE_DENIED", "task_id": task_id,
                        "target_path": data.get("target_path")})
            return {"status": "MANUAL_REVIEW_REQUIRED", "task_id": task_id,
                    "target_path": data.get("target_path")}

        if data.get("blocked"):
            result = {
                "status": "MANUAL_REVIEW_REQUIRED",
                "task_id": task_id,
                "target_path": data["target_path"],
                "message": (
                    f"'{data['target_path']}' resolves to a blocked or repo-escaping path; "
                    "automatic apply is forbidden. Owner review is required."
                ),
            }
            self._log({"action": "APPROVE_BLOCKED", "task_id": task_id,
                        "target_path": data["target_path"]})
            return result

        decision = self.classify_target(data["target_path"])
        target = self.repo_root / decision["normalized_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data["content"], encoding="utf-8")

        data["status"] = "APPROVED"
        data["approved_at"] = datetime.now().isoformat()
        data["approved_automatically"] = automatic

        new_path = self._proposal_path(task_id, status="APPROVED")
        new_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        proposal_path.unlink()

        self._log({"action": "AUTO_APPROVE" if automatic else "APPROVE",
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
        self._log({"action": "REJECT", "task_id": task_id, "target_path": data["target_path"]})
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
            flag = "BLOCKED" if p.get("blocked") else "manual review"
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
    assert (gate.repo_root / safe_target).exists()
    assert (gate.proposals_dir / "Approved" / f"{safe_id}.proposal.json").exists()

    blocked_id = "GATE-TEST-BLOCKED"
    blocked_target = "03_Bot/should_never_write.py"
    blocked = gate.propose(blocked_id, "blocked test", blocked_target)
    assert blocked["blocked"] is True
    assert blocked["auto_approved"] is False
    assert not (gate.repo_root / blocked_target).exists()
    assert gate.approve(blocked_id)["status"] == "MANUAL_REVIEW_REQUIRED"
    gate.reject(blocked_id)

    manual_id = "GATE-TEST-MANUAL"
    manual_target = "15_AI_Brain/Control/should_not_auto_write.py"
    manual = gate.propose(manual_id, "manual test", manual_target)
    assert manual["auto_approved"] is False
    assert not (gate.repo_root / manual_target).exists()
    gate.reject(manual_id)

    escape_id = "GATE-TEST-ESCAPE"
    escape_target = "15_AI_Brain/Outputs/../../03_Bot/escape.py"
    escape = gate.propose(escape_id, "escape test", escape_target)
    assert escape["blocked"] is True
    assert escape["auto_approved"] is False
    assert not (gate.repo_root / "03_Bot" / "escape.py").exists()
    gate.reject(escape_id)

    print("ALL CONFIRM GATE SELF-TESTS PASSED")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        _cli()
    else:
        _self_test()
