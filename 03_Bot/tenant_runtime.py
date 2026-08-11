"""Tenant resolution and request-local clinic binding."""

from __future__ import annotations

import contextvars
import threading
import time
from dataclasses import dataclass

import gspread


class TenantAccessError(RuntimeError):
    """An update cannot be mapped to exactly one active clinic."""


@dataclass(frozen=True, slots=True)
class TenantIdentity:
    clinic_id: str
    clinic_name: str
    sheet_id: str
    latitude: float = 0.0
    longitude: float = 0.0
    attendance_radius_m: float = 200.0
    attendance_max_accuracy_m: float = 100.0

    def __post_init__(self) -> None:
        if not self.clinic_id.strip() or not self.sheet_id.strip():
            raise ValueError("Tenant identity requires clinic_id and sheet_id")


_active_tenant: contextvars.ContextVar[TenantIdentity | None] = contextvars.ContextVar(
    "relife_active_tenant", default=None
)


def bind_tenant(tenant: TenantIdentity) -> contextvars.Token:
    return _active_tenant.set(tenant)


def reset_tenant(token: contextvars.Token) -> None:
    _active_tenant.reset(token)


def current_tenant() -> TenantIdentity:
    tenant = _active_tenant.get()
    if tenant is None:
        raise TenantAccessError("Clinic tenant has not been resolved for this operation")
    return tenant


class MasterTenantResolver:
    """Resolve Telegram users using private Clinics and Staff_Directory tabs."""

    REQUIRED_CLINIC_COLUMNS = {"Clinic_ID", "Clinic_Name", "Sheet_ID", "Status"}
    REQUIRED_STAFF_COLUMNS = {"Telegram_ID", "Clinic_ID", "Status"}

    def __init__(self, client: gspread.Client, master_sheet_id: str, *, cache_ttl: float = 30.0):
        if not master_sheet_id:
            raise ValueError("MASTER_SHEET_ID is required")
        self._spreadsheet = client.open_by_key(master_sheet_id)
        self._cache_ttl = max(0.0, cache_ttl)
        self._cache: dict[str, TenantIdentity] = {}
        self._tenants: tuple[TenantIdentity, ...] = ()
        # Force the first read even on a freshly booted host whose monotonic
        # clock is still lower than cache_ttl.
        self._cache_time = float("-inf")
        self._lock = threading.RLock()

    @staticmethod
    def _active(value: object) -> bool:
        return str(value).strip().casefold() == "active"

    @staticmethod
    def _validate_columns(headers: list[str], required: set[str], tab: str) -> None:
        missing = required.difference(headers)
        if missing:
            raise TenantAccessError(
                f"Master tab {tab} is missing columns: {', '.join(sorted(missing))}"
            )

    def _reload(self) -> None:
        clinics_ws = self._spreadsheet.worksheet("Clinics")
        staff_ws = self._spreadsheet.worksheet("Staff_Directory")
        self._validate_columns(
            clinics_ws.row_values(1), self.REQUIRED_CLINIC_COLUMNS, "Clinics"
        )
        self._validate_columns(
            staff_ws.row_values(1), self.REQUIRED_STAFF_COLUMNS, "Staff_Directory"
        )
        clinics = clinics_ws.get_all_records()
        staff_rows = staff_ws.get_all_records()

        clinics_by_id: dict[str, TenantIdentity] = {}
        sheet_ids: set[str] = set()
        for row in clinics:
            if not self._active(row.get("Status")):
                continue
            clinic_id = str(row.get("Clinic_ID", "")).strip()
            sheet_id = str(row.get("Sheet_ID", "")).strip()
            if not clinic_id or not sheet_id:
                raise TenantAccessError("Active clinic has blank Clinic_ID or Sheet_ID")
            if clinic_id in clinics_by_id or sheet_id in sheet_ids:
                raise TenantAccessError("Duplicate active Clinic_ID or Sheet_ID in master")
            try:
                clinics_by_id[clinic_id] = TenantIdentity(
                    clinic_id,
                    str(row.get("Clinic_Name", "")).strip(),
                    sheet_id,
                    float(row.get("Latitude", 0) or 0),
                    float(row.get("Longitude", 0) or 0),
                    float(row.get("Attendance_Radius_M", 200) or 200),
                    float(row.get("Attendance_Max_Accuracy_M", 100) or 100),
                )
            except (TypeError, ValueError) as error:
                raise TenantAccessError(
                    f"Clinic {clinic_id} has invalid attendance coordinates/settings"
                ) from error
            sheet_ids.add(sheet_id)

        resolved: dict[str, TenantIdentity] = {}
        for row in staff_rows:
            if not self._active(row.get("Status")):
                continue
            telegram_id = str(row.get("Telegram_ID", "")).strip()
            clinic_id = str(row.get("Clinic_ID", "")).strip()
            if not telegram_id or clinic_id not in clinics_by_id:
                continue
            if telegram_id in resolved:
                raise TenantAccessError("Duplicate active Telegram_ID mapping in master")
            resolved[telegram_id] = clinics_by_id[clinic_id]

        self._cache = resolved
        self._tenants = tuple(clinics_by_id.values())
        self._cache_time = time.monotonic()

    def resolve(self, telegram_id: int | str) -> TenantIdentity | None:
        with self._lock:
            if time.monotonic() - self._cache_time >= self._cache_ttl:
                self._reload()
            return self._cache.get(str(telegram_id).strip())

    def invalidate(self) -> None:
        with self._lock:
            self._cache_time = 0.0

    def list_active_tenants(self) -> tuple[TenantIdentity, ...]:
        with self._lock:
            if time.monotonic() - self._cache_time >= self._cache_ttl:
                self._reload()
            return self._tenants
