#!/usr/bin/env python3
"""Cross-process lock for BrainOS mutating workflows."""

from __future__ import annotations

import fcntl
from pathlib import Path


class LockBusyError(RuntimeError):
    pass


class BrainOSLock:
    """Non-blocking OS file lock released automatically on process exit."""

    def __init__(self, path: Path | None = None):
        root = Path(__file__).resolve().parents[3]
        self.path = path or root / "development/15_AI_Brain" / "Logs" / "brainos.lock"
        self._handle = None

    def acquire(self) -> "BrainOSLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.close()
            raise LockBusyError("another BrainOS process holds the execution lock") from exc
        self._handle = handle
        return self

    def release(self) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "BrainOSLock":
        return self.acquire()

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()
