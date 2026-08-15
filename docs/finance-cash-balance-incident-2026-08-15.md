# Cash balance incident — 2026-08-15

## Symptom
Telegram `💰 এখন কত আছে (Live)` showed inflated Reception cash because `07_Expenses` could no longer be parsed as a normal A1 table.

## Root cause
Two pending expense writes were appended to the right of the canonical A:AB headers instead of starting at column A. That widened the used range with blank header cells. `safe_get_all_records()` intentionally fails closed on a gspread read error, so the cash summary received an empty expense list and therefore did not deduct paid Reception/Home Treasury expenses.

The Relife runtime now anchors implicit `Worksheet.append_row()` calls to the logical table at `A1` while preserving callers that explicitly provide another `table_range`.

## Recovery
The displaced pending expense rows must be moved back under A:AB, the duplicate second Expense ID must be corrected, and the stray cells to the right must be cleared. After that, the live finance read sees expenses again and the normal custody formula applies:

- Reception += cash collections
- Reception -= paid Reception expenses
- Reception -= accepted handovers out
- Home Treasury += accepted handovers in
- Home Treasury -= paid Home expenses / household withdrawals / Home-paid salaries
- Transfers remain custody movements, not business expenses
