# Live Google Sheets Schema Audit

`audit_live_schema.py` performs a read-only structural audit of the workbook
used by the production bot. It requests the Google Sheets read-only scope and
does not call update, append, clear, delete, resize, or batch-update methods.

It checks all configured operational tabs from `02_Patients` through
`20_Data_Audit` and reports only counts and schema defects:

- missing tabs;
- blank or duplicate headers;
- missing Unified Data Contract headers;
- rows wider than the header row;
- duplicate values in the first `*_ID` column;
- common Google Sheets formula errors.

Cell values, patient names, phone numbers, clinical notes, and payment details
are never included in the report.

Run from the repository root:

```bash
python 05_GoogleSheets/audit_live_schema.py --output live-schema-audit.json
```

Exit code `0` means no structural defect was found. Exit code `1` means the
report needs review; it does not modify the workbook.
