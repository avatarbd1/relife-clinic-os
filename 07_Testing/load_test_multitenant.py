"""Offline 20-clinic concurrency/isolation simulation; never calls Google or Telegram."""

from __future__ import annotations

import argparse
import asyncio
import random
import os
import statistics
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1] / "03_Bot"
sys.path.insert(0, str(BOT_DIR))
os.environ.setdefault("BOT_TOKEN", "123456:TESTTOKEN")
os.environ.setdefault("GOOGLE_SHEET_ID", "LOAD_TEST_LEGACY")
os.environ.setdefault("GOOGLE_CREDENTIALS_PATH", __file__)
os.environ["MULTITENANT_ENABLED"] = "true"
os.environ.setdefault("MASTER_SHEET_ID", "LOAD_TEST_MASTER")

from tenant_runtime import TenantIdentity, bind_tenant, current_tenant, reset_tenant
import async_runtime


class FakeTenantStore:
    def __init__(self):
        self.rows = defaultdict(list)
        self.guard = threading.Lock()

    def check_in(self, staff_id: str):
        tenant = current_tenant()
        time.sleep(random.uniform(0.03, 0.12))
        row = {
            "clinic_id": tenant.clinic_id,
            "sheet_id": tenant.sheet_id,
            "staff_id": staff_id,
            "patient_id": "PT0001",  # deliberately collides across clinics
            "sentinel": f"{tenant.clinic_id}_SECRET_SENTINEL",
        }
        with self.guard:
            self.rows[tenant.clinic_id].append(row)
        return row


async def run(clinics: int, staff_per_clinic: int):
    store = FakeTenantStore()
    latencies = []

    async def one_check_in(clinic_number: int, staff_number: int):
        tenant = TenantIdentity(
            f"C{clinic_number:02d}",
            f"Clinic {clinic_number:02d}",
            f"SHEET_{clinic_number:02d}",
        )
        token = bind_tenant(tenant)
        started = time.perf_counter()
        try:
            row = await async_runtime.run_sheets_write(
                store.check_in, f"STAFF_{staff_number:02d}"
            )
            assert row["clinic_id"] == tenant.clinic_id
            assert row["sheet_id"] == tenant.sheet_id
        finally:
            reset_tenant(token)
            latencies.append(time.perf_counter() - started)

    await asyncio.gather(*(
        one_check_in(c, s)
        for c in range(1, clinics + 1)
        for s in range(1, staff_per_clinic + 1)
    ))

    for clinic_id, rows in store.rows.items():
        expected = f"{clinic_id}_SECRET_SENTINEL"
        assert all(row["sentinel"] == expected for row in rows), "cross-tenant leak"
        assert len({row["staff_id"] for row in rows}) == staff_per_clinic

    ordered = sorted(latencies)
    p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
    print(f"PASS clinics={clinics} operations={len(latencies)}")
    print(f"latency_ms median={statistics.median(latencies)*1000:.1f} p95={p95*1000:.1f}")
    print("cross_tenant_leaks=0 duplicate_staff_checkins=0")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clinics", type=int, default=20)
    parser.add_argument("--staff-per-clinic", type=int, default=10)
    args = parser.parse_args()
    asyncio.run(run(args.clinics, args.staff_per_clinic))


if __name__ == "__main__":
    main()

