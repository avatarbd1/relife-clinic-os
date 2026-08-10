# Multi-tenant operations

The bot resolves every Telegram update through a private master spreadsheet before
any clinic sheet can be opened. Multi-tenant mode has no default-sheet fallback.

## Master directory

Create it automatically from the current production clinic:

```powershell
python 03_Bot/bootstrap_multitenant.py --dry-run
python 03_Bot/bootstrap_multitenant.py
```

The script creates:

- `Clinics`: `Clinic_ID`, `Clinic_Name`, `Sheet_ID`, `Status`, `Credential_Ref`,
  `Latitude`, `Longitude`, `Attendance_Radius_M`,
  `Attendance_Max_Accuracy_M`, `Created_At`, `Updated_At`.
- `Staff_Directory`: `Telegram_ID`, `Clinic_ID`, `Staff_ID`, `Status`, `Updated_At`.

`Telegram_ID`, active `Clinic_ID`, and active `Sheet_ID` mappings must be unique.
Duplicate active mappings make resolution fail closed. Never share the master
spreadsheet with a clinic.

## Environment

Keep `MULTITENANT_ENABLED=false` through staging and add:

```env
MASTER_SHEET_ID=...
TEMPLATE_SHEET_ID=...
CLINIC_SHEETS_FOLDER_ID=...
TENANT_LOOKUP_CACHE_TTL=30
SHEETS_READ_CONCURRENCY_LIMIT=4
SHEETS_WRITE_CONCURRENCY_LIMIT=4
SHEETS_READ_REQUESTS_PER_MINUTE=240
SHEETS_READ_BURST=20
SHEETS_WRITE_REQUESTS_PER_MINUTE=45
SHEETS_WRITE_BURST=5
```

After staging verification, set `MULTITENANT_ENABLED=true`. `GOOGLE_SHEET_ID`
remains only as a rollback setting while the flag is false.

## Provision a clinic

```powershell
python 03_Bot/provision_clinic.py "XYZ Clinic" --dry-run
python 03_Bot/provision_clinic.py "XYZ Clinic"
```

The real run copies `00_Template`, verifies service-account write access, and adds
the clinic to the master `Clinics` tab. Add its first administrator to
`Staff_Directory` before they use the bot. Attendance remains unavailable until
that clinic's latitude and longitude are configured.

## Verification

Offline tests never contact Google or Telegram:

```powershell
python -m pytest 07_Testing/test_multitenant_isolation.py -q
python 07_Testing/load_test_multitenant.py
```

The load harness defaults to 20 clinics × 10 simultaneous staff and deliberately
uses the same `PT0001` identifier in every clinic to catch cross-tenant mixing.

Keep PTB update processing sequential. The bot intentionally does not enable
`concurrent_updates=True`, because its `ConversationHandler` state depends on
ordered updates. Blocking Sheet writes run in bounded worker threads, and writes
for the same clinic are serialized.
