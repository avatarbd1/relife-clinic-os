#!/usr/bin/env python3
"""Send BrainOS failure alerts to the clinic owner via Telegram.

This module deliberately does not import ``03_Bot``.  It reuses the same
``BOT_TOKEN`` environment variable and accepts a dedicated owner chat id from
``BRAIN_ALERT_CHAT_ID`` (with conservative legacy fallbacks).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # Environment variables may already be exported by the service.
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")


CHAT_ID_KEYS = ("BRAIN_ALERT_CHAT_ID", "OWNER_TELEGRAM_ID", "TELEGRAM_CHAT_ID")


@dataclass(frozen=True)
class AlertResult:
    sent: bool
    status: str
    detail: str = ""


def _chat_id() -> str:
    for key in CHAT_ID_KEYS:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def send_alert(title: str, detail: str, task_id: str = "", stage: str = "") -> AlertResult:
    """Send one concise alert. Missing configuration is a safe no-op."""
    token = os.getenv("BOT_TOKEN", "").strip()
    chat_id = _chat_id()
    if not token or not chat_id:
        return AlertResult(False, "SKIPPED", "BOT_TOKEN or owner chat id is not configured")

    lines = [f"⚠️ AI Brain — {title}"]
    if task_id:
        lines.append(f"Task: {task_id}")
    if stage:
        lines.append(f"Stage: {stage}")
    lines.append(f"Detail: {detail[:1200]}")
    lines.append("Action: Owner review needed")

    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": "\n".join(lines)}).encode()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    request = urllib.request.Request(url, data=payload, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
        if body.get("ok"):
            return AlertResult(True, "SENT")
        return AlertResult(False, "FAILED", "Telegram API returned ok=false")
    except Exception as exc:
        # Never expose request URL/token in the returned error.
        return AlertResult(False, "FAILED", f"{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    result = send_alert("Alert test", "BrainOS alert notifier is reachable.", stage="manual-test")
    print(f"Alert status: {result.status} ({result.detail})")
