# Attendance Location Hardening Plan

**Status:** Proposed  
**Scope:** Plan only; no production behavior change  
**Baseline:** `main` at `c6cdadfe164a117cf54f89e9e85844b249aed333`  
**Reviewed:** 2026-08-11

## Verified baseline

- Attendance label routing regression commit `486022626e49d65c66322c645e0d8c76e04e736b` is an ancestor of the baseline main commit.
- Both `🕐 হাজিরা` and legacy `🏠 হাজিরা` are included in `_ATTENDANCE_MENU_LABELS`.
- Both labels are escaped into `_ATTENDANCE_MENU_REGEX` and routed to the same `attendance_menu` handler.
- Production Bot CI-equivalent local verification passed: production module compile plus all 57 workflow-listed tests.
- Existing location tests cover inside/outside radius, low accuracy, missing configuration, Telegram handler wiring, and audit-note persistence.

## Current risks and gaps

### H1 — Unknown or malformed accuracy can be accepted

`validate_location()` rejects accuracy only when it is present and above the threshold. A missing accuracy value is accepted, and negative/non-finite values are not explicitly rejected.

**Required behavior:** fail closed for missing, negative, NaN, infinite, or otherwise invalid accuracy.

### H2 — Accuracy-overlap rule broadens the geofence

The current calculation subtracts reported accuracy from distance:

`effective_distance = max(0, distance - accuracy)`

This may accept a point whose reported center lies outside the configured clinic radius when its accuracy circle overlaps the radius.

**Decision required before implementation:** choose and document a conservative rule. Recommended default: reported center must be within the configured radius and accuracy must independently be at or below the maximum. Do not enlarge the radius by reported uncertainty.

### H3 — Check-in duplicate protection is not atomic

`attendance_check_in()` performs read-then-append. Concurrent location submissions can both observe no existing row before either append completes. Current bot handlers use `block=False`, so the duplicate guard must not rely only on global update ordering.

**Required behavior:** enforce idempotency with a staff/date key and a process lock or atomic persistence strategy; re-check inside the critical section immediately before append.

### H4 — Location request state is weakly bound

The pending state stores only a timestamp in `context.user_data`. It is not explicitly bound to staff ID, tenant/clinic ID, request ID, or originating action/message.

**Required behavior:** store a short-lived request record containing nonce, staff ID, tenant/clinic ID, issued timestamp, expiry, and consumed state. Validate every field before accepting a location.

### M1 — Configuration bounds are incomplete

Radius, maximum accuracy, and clinic coordinates are parsed but not comprehensively validated for finite numeric values and safe ranges. The current truthiness check also treats a zero latitude or longitude as unconfigured.

**Required behavior:** validate finite WGS84 coordinates independently; define allowed radius and accuracy bounds; reject invalid tenant configuration fail closed.

### M2 — Precise coordinates are stored in a free-text note

The audit note stores latitude and longitude to six decimals alongside distance and accuracy. This is sensitive location data and is difficult to query, retain, or redact safely when embedded in free text.

**Required behavior:** define structured audit columns and a retention/access policy. Prefer storing the minimum evidence required (decision, distance bucket or distance, accuracy, timestamp, clinic configuration version, verifier version). Store raw coordinates only if explicitly approved and protected.

### M3 — Retry and denial audit coverage is limited

The request timestamp is consumed before validation. Failed low-accuracy/outside attempts cannot be correlated with a request and there is no structured denial audit.

**Required behavior:** record privacy-minimized denial reason and request ID; define whether a failed attempt may retry within the original expiry or must request a new challenge.

### M4 — Checkout policy is undefined

Check-in is location-gated while checkout and break actions are not. This may be intentional, but it is not documented.

**Required behavior:** record an owner decision for check-out/break geofencing and test the chosen policy.

## Proposed implementation sequence

### PR A — Pure validation hardening

- Reject missing/non-finite/negative accuracy.
- Validate coordinate, radius, and maximum-accuracy configuration.
- Replace the overlap-expansion rule with the approved conservative rule.
- Add boundary tests for exact radius, exact accuracy threshold, NaN/infinity, invalid ranges, zero-valued valid coordinates, and malformed settings.
- No sheet migration and no menu change.

### PR B — Request binding and replay protection

- Introduce a typed pending attendance-location request.
- Bind it to staff, tenant, expiry, and a one-time nonce.
- Consume exactly once.
- Deny stale, mismatched, replayed, or absent requests.
- Add callback/direct-message/replay regression tests.

### PR C — Atomic check-in idempotency

- Serialize staff/date check-in creation across asynchronous handlers.
- Re-read under the critical section before append.
- Return the existing record deterministically for duplicates.
- Add simultaneous-submission tests.
- Document limitations of Google Sheets as a datastore and the safe fallback behavior.

### PR D — Structured audit and privacy controls

- Add approved audit fields and migration tooling.
- Minimize or remove raw coordinates according to the approved retention policy.
- Add permission, redaction, retention, and migration tests.
- Run migration dry-run and reconciliation before enabling new writes.

### PR E — Optional checkout/break policy

Only if the owner approves location enforcement for checkout or break actions. Keep this separate from check-in hardening.

## Security and rollout gates

- Every missing or malformed security input fails closed.
- No direct edit to `main`.
- Each implementation PR is small, independently reviewable, and covered by regression tests.
- Existing `🕐 হাজিরা` and `🏠 হাজিরা` routing remains unchanged.
- No live Sheet migration without backup, schema snapshot, dry-run, reconciliation, and rollback instructions.
- CI must pass before merge.
- Deploy progressively and verify the health endpoint plus one controlled attendance flow.
- Never treat Telegram-provided GPS as tamper-proof; this control reduces accidental/off-site check-ins but cannot prove physical presence against a compromised or spoofed device.

## Decisions needed before PR A/D/E

1. Geofence rule: recommended center-point distance within radius plus independent accuracy threshold.
2. Raw coordinate storage: recommended do not retain raw coordinates after decision unless a documented operational need is approved.
3. Denied-attempt retention period and who may view it.
4. Whether checkout and break actions require location.
