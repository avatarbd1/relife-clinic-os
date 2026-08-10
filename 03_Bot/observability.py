"""Privacy-minimized, optional Sentry error reporting."""

from __future__ import annotations

import os
import re
from typing import Any

try:
    import sentry_sdk
except ImportError:  # Bot must still start when observability is unavailable.
    sentry_sdk = None


_BD_PHONE = re.compile(r"(?<!\d)(?:\+?880|0)?1[3-9]\d{8}(?!\d)")
_SENSITIVE_KEYS = {
    "address", "alternate_phone", "alternative_phone", "bot_token", "diagnosis",
    "email", "full_name", "message", "message_text", "name", "patient",
    "patient_name", "phone", "staff", "telegram_update", "text", "token", "update",
}


def _scrub(value: Any, key: str = "") -> Any:
    if key.lower() in _SENSITIVE_KEYS:
        return "[Filtered]"
    if isinstance(value, dict):
        return {k: _scrub(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scrub(item) for item in value)
    if isinstance(value, str):
        return _BD_PHONE.sub("[Filtered phone]", value)
    return value


def _before_send(event: dict, hint: dict) -> dict:
    # Telegram updates, users, HTTP request data, breadcrumbs, and arbitrary
    # extras are unnecessary for locating a Python exception and may contain PII.
    for field in ("request", "user", "breadcrumbs", "extra"):
        event.pop(field, None)
    return _scrub(event)


def init_sentry() -> bool:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn or sentry_sdk is None:
        return False
    try:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
            release=os.getenv("RENDER_GIT_COMMIT") or os.getenv("SENTRY_RELEASE"),
            send_default_pii=False,
            include_local_variables=False,
            max_breadcrumbs=0,
            traces_sample_rate=0.0,
            before_send=_before_send,
        )
        return True
    except Exception:
        return False


def capture_exception(error: BaseException) -> None:
    if sentry_sdk is None or not os.getenv("SENTRY_DSN", "").strip():
        return
    try:
        sentry_sdk.capture_exception(error)
    except Exception:
        pass
