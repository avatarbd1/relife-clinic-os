"""Relife Unified Data Contract v1."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

SCHEMA_VERSION = "relife-uda-v1"

ORGANIZATION_ID = os.getenv(
    "RELIFE_ORGANIZATION_ID", "RELIFE"
)
CLINIC_ID = os.getenv(
    "RELIFE_CLINIC_ID", "RELIFE-PHYSIO"
)
BRANCH_ID = os.getenv(
    "RELIFE_BRANCH_ID", "AMTALI-01"
)

UNIFIED_HEADERS = [
    "Organization_ID",
    "Clinic_ID",
    "Branch_ID",
    "Record_ID",
    "Encounter_ID",
    "Provider_ID",
    "Source_System",
    "Source_Type",
    "AI_Generated",
    "Human_Verified",
    "Schema_Version",
    "Provenance_Timestamp",
]


def _bd_timestamp():
    tz = timezone(timedelta(hours=6))
    return datetime.now(tz).isoformat(timespec="seconds")


def new_record_id(record_type):
    prefix = "".join(
        ch for ch in record_type.upper()
        if ch.isalnum()
    )[:8] or "REC"

    return f"{prefix}-{uuid.uuid4().hex[:16].upper()}"


def encounter_id_from_treatment(treatment_id):
    if treatment_id:
        return f"ENC-{treatment_id}"

    return new_record_id("ENC")


def metadata(
    record_type,
    *,
    legacy_record_id="",
    encounter_id="",
    provider_id="",
    source_system="telegram_bot",
    source_type="human_entry",
    ai_generated=False,
    human_verified=True,
):
    if legacy_record_id:
        record_id = f"{CLINIC_ID}:{legacy_record_id}"
    else:
        record_id = new_record_id(record_type)

    return {
        "Organization_ID": ORGANIZATION_ID,
        "Clinic_ID": CLINIC_ID,
        "Branch_ID": BRANCH_ID,
        "Record_ID": record_id,
        "Encounter_ID": encounter_id,
        "Provider_ID": provider_id,
        "Source_System": source_system,
        "Source_Type": source_type,
        "AI_Generated":
            "TRUE" if ai_generated else "FALSE",
        "Human_Verified":
            "TRUE" if human_verified else "FALSE",
        "Schema_Version": SCHEMA_VERSION,
        "Provenance_Timestamp": _bd_timestamp(),
    }


def apply_to_headers(headers, row, envelope):
    result = list(row)

    if len(result) < len(headers):
        result.extend(
            [""] * (len(headers) - len(result))
        )

    for key, value in envelope.items():
        if key in headers:
            result[headers.index(key)] = value

    return result
