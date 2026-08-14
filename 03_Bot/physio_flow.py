"""Pure Physio floor-allocation helpers.

The Telegram and Sheets layers both use these helpers so booking, today's queue
and the therapist dashboard interpret reservations identically.
"""
from __future__ import annotations

import re


ACTIVE_STATUSES = {"scheduled", "waiting", "in treatment", "arrived"}
ROOMS = ("Room 1", "Room 2")
BEDS = {"Room 1": ("Bed 1", "Bed 2"), "Room 2": ("Bed 3", "Bed 4")}
FLOW_TAG_RE = re.compile(r"\[PTFLOW\s+([^\]]+)\]", re.IGNORECASE)


class PhysioCapacityError(ValueError):
    """No gender-compatible resource is available for the requested slot."""


def normalize_gender(value: object) -> str:
    text = str(value or "").strip().casefold()
    if text in {"male", "m", "পুরুষ", "ছেলে"}:
        return "Male"
    if text in {"female", "f", "মহিলা", "নারী", "মেয়ে", "মেয়ে"}:
        return "Female"
    return ""


def flow_fields(appointment: dict) -> dict[str, str]:
    """Read native columns first, then the backwards-compatible Remarks tag."""
    fields = {
        "Gender": str(appointment.get("Gender", "") or "").strip(),
        "Room": str(appointment.get("Room", "") or "").strip(),
        "Bed": str(appointment.get("Bed", "") or "").strip(),
        "Station": str(appointment.get("Station", "") or "").strip(),
    }
    match = FLOW_TAG_RE.search(str(appointment.get("Remarks", "") or ""))
    if match:
        parsed = {}
        for part in match.group(1).split(";"):
            key, sep, value = part.partition("=")
            if sep:
                parsed[key.strip().casefold()] = value.strip()
        for header in fields:
            if not fields[header]:
                fields[header] = parsed.get(header.casefold(), "")
    fields["Gender"] = normalize_gender(fields["Gender"])
    return fields


def with_flow_tag(remarks: object, assignment: dict[str, str]) -> str:
    clean = FLOW_TAG_RE.sub("", str(remarks or "")).strip()
    tag = "[PTFLOW " + ";".join(
        f"{key.casefold()}={assignment.get(key, '')}"
        for key in ("Gender", "Room", "Bed", "Station")
    ) + "]"
    return f"{clean} {tag}".strip()


def _same_slot(row: dict, date_str: str, time_str: str) -> bool:
    return (
        str(row.get("Department", "")).strip() == "Physio"
        and str(row.get("Date", "")).strip() == str(date_str).strip()
        and str(row.get("Time", "")).strip() == str(time_str).strip()
        and str(row.get("Status", "Scheduled")).strip().casefold() in ACTIVE_STATUSES
    )


def allocate_resource(
    appointments: list[dict], date_str: str, time_str: str,
    gender: object, *, needs_traction: bool = False,
) -> dict[str, str]:
    """Allocate one traction bed or a gender-compatible treatment-room bed."""
    normalized = normalize_gender(gender)
    if not normalized:
        raise PhysioCapacityError("রোগীর Gender দেওয়া নেই। Patient profile আগে ঠিক করুন।")

    slot = [r for r in appointments if _same_slot(r, date_str, time_str)]
    occupied = [flow_fields(r) for r in slot]
    if needs_traction:
        if any(item["Station"] == "Traction" for item in occupied):
            raise PhysioCapacityError("এই সময়ে Traction Bed আগে থেকেই বুক করা।")
        return {"Gender": normalized, "Room": "Traction Room", "Bed": "Traction Bed", "Station": "Traction"}

    room_genders = {room: set() for room in ROOMS}
    occupied_beds = set()
    for item in occupied:
        room = item["Room"]
        bed = item["Bed"]
        if room in room_genders and item["Gender"]:
            room_genders[room].add(item["Gender"])
        if bed:
            occupied_beds.add(bed)

    # Fill an already matching room first; otherwise lock an empty room.
    preferred = [room for room in ROOMS if room_genders[room] == {normalized}]
    preferred += [room for room in ROOMS if not room_genders[room]]
    for room in preferred:
        for bed in BEDS[room]:
            if bed not in occupied_beds:
                return {"Gender": normalized, "Room": room, "Bed": bed, "Station": "Treatment"}
    raise PhysioCapacityError("এই সময়ে Gender-compatible Treatment Bed খালি নেই।")
