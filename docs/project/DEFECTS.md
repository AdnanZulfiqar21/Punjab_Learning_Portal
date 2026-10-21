# DEFECTS

The defect register (P00.S3.T2, SEVERITY-01). Severities and owners are in `SEVERITY_AND_GATES.md`.

- Record one row per P0 or P1 defect, and per P2 or P3 when it is listed as a launch limitation.
- Status is `OPEN`, `FIXED` (fixed and retested; name the evidence) or `WONT_FIX` (P2/P3 only, with the reason).
- The readiness guard (`apps/api/tests/test_readiness_claims.py`) refuses a readiness claim while any P0 or P1 row is `OPEN`.

No defect has been recorded yet. That is not evidence that none exists: a triage pass must record every defect found before any release.

| ID | Severity | Title | Found | Owner | Status | Evidence |
|---|---|---|---|---|---|---|
