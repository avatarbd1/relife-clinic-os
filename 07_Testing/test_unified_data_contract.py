import sys
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1] / "03_Bot"
sys.path.insert(0, str(BOT_DIR))

from data_contract import (  # noqa: E402
    CLINIC_ID,
    SCHEMA_VERSION,
    apply_to_headers,
    encounter_id_from_treatment,
    metadata,
)


def test_legacy_id_is_namespaced_for_multi_clinic_merge():
    envelope = metadata("patient", legacy_record_id="PT0001")
    assert envelope["Record_ID"] == f"{CLINIC_ID}:PT0001"
    assert envelope["Schema_Version"] == SCHEMA_VERSION


def test_treatment_has_stable_encounter_id():
    assert encounter_id_from_treatment("TR0042") == "ENC-TR0042"


def test_metadata_overlay_is_backward_compatible():
    legacy_headers = ["Patient_ID", "Full_Name"]
    legacy_row = ["PT0001", "Example"]
    envelope = metadata("patient", legacy_record_id="PT0001")
    assert apply_to_headers(legacy_headers, legacy_row, envelope) == legacy_row


def test_metadata_fills_only_migrated_headers():
    headers = ["Treatment_ID", "Patient_ID", "Clinic_ID", "Record_ID", "Schema_Version"]
    envelope = metadata("treatment", legacy_record_id="TR0001")
    row = apply_to_headers(headers, ["TR0001", "PT0001"], envelope)
    assert row[2] == CLINIC_ID
    assert row[3] == f"{CLINIC_ID}:TR0001"
    assert row[4] == SCHEMA_VERSION
