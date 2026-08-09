import asyncio
import importlib.util
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "03_Bot" / "async_runtime.py"
SPEC = importlib.util.spec_from_file_location("async_runtime", MODULE_PATH)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runtime)


class AsyncRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_blocking_call_runs_outside_event_loop_thread(self):
        loop_thread = threading.get_ident()
        worker_thread = await runtime.AsyncCallGate(1).run(threading.get_ident)
        self.assertNotEqual(worker_thread, loop_thread)

    async def test_concurrency_limit_is_enforced(self):
        gate = runtime.AsyncCallGate(2)
        lock = threading.Lock()
        active = 0
        peak = 0

        def blocking_work():
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.03)
            with lock:
                active -= 1

        await asyncio.gather(*(gate.run(blocking_work) for _ in range(6)))
        self.assertEqual(peak, 2)

    async def test_timeout_returns_control_to_event_loop(self):
        gate = runtime.AsyncCallGate(1)
        started = time.monotonic()
        with self.assertRaises(asyncio.TimeoutError):
            await gate.run(time.sleep, 0.2, timeout=0.02)
        self.assertLess(time.monotonic() - started, 0.15)

    async def test_background_success_is_delivered(self):
        delivered = []

        async def success(value):
            delivered.append(("success", value))

        async def error(reason):
            delivered.append(("error", reason))

        await runtime.run_ai_background(
            lambda: "ready",
            on_success=success,
            on_error=error,
        )
        self.assertEqual(delivered, [("success", "ready")])

    async def test_background_error_is_user_safe(self):
        delivered = []

        def fail():
            raise RuntimeError("secret provider detail")

        async def success(value):
            delivered.append(("success", value))

        async def error(reason):
            delivered.append(("error", reason))

        await runtime.run_ai_background(
            fail,
            on_success=success,
            on_error=error,
        )
        self.assertEqual(delivered, [("error", "error")])


if __name__ == "__main__":
    unittest.main()
