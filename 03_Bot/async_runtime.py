"""Bounded adapters for running blocking SDK/network calls off the bot loop."""

from __future__ import annotations

import asyncio
import os
from functools import partial
from typing import Any, Callable


class AsyncCallGate:
    """Run synchronous callables in worker threads with bounded concurrency."""

    def __init__(self, limit: int):
        self.limit = max(1, limit)
        self._semaphore: asyncio.Semaphore | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _gate(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._loop is not loop:
            self._loop = loop
            self._semaphore = asyncio.Semaphore(self.limit)
        return self._semaphore

    async def run(
        self,
        function: Callable[..., Any],
        /,
        *args: Any,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        call = partial(function, *args, **kwargs)
        async with self._gate():
            work = asyncio.to_thread(call)
            if timeout is None:
                return await work
            return await asyncio.wait_for(work, timeout=timeout)


AI_GATE = AsyncCallGate(int(os.getenv("AI_CONCURRENCY_LIMIT", "2")))
ROLE_GATE = AsyncCallGate(int(os.getenv("ROLE_LOOKUP_CONCURRENCY_LIMIT", "4")))


async def run_ai(function, /, *args, timeout: float = 120, **kwargs):
    return await AI_GATE.run(function, *args, timeout=timeout, **kwargs)


async def run_role_lookup(function, /, *args, timeout: float = 20, **kwargs):
    return await ROLE_GATE.run(function, *args, timeout=timeout, **kwargs)
