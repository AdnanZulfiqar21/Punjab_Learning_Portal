# Local API suite run of 2026-10-14: 43 tests, 7 failed

**Finding:** an environment failure, not a product defect. The machine ran out of commit memory (RAM plus page file)
while the suite was running. pytest stopped with `INTERNALERROR> MemoryError` after 43 of 667 tests. The names of the 7
failed tests weren't kept, so which tests failed and how is not known. The section "What is not known" says what that
leaves open.

## The failing run

- **Command** (background task `bcb7focgm`, started 2026-10-14 21:10:58 UTC), in `apps/api` on `feat/marking-time` at
  `a7e611d`:
  `timeout 2700 uv run --no-sync python -m pytest -p no:cacheprovider -o faulthandler_timeout=300 2>&1 | tail -4`
- **Everything that was kept** (finished 21:12:51 UTC):

  ```text
  INTERNALERROR>                    _feature_version=feature_version, optimize=optimize)
  INTERNALERROR> MemoryError

  7 failed, 36 passed in 104.37s (0:01:44)
  ```

- **The "exit code 0" was tail's.** The pipe had no `pipefail`, so pytest's own exit status was lost. Only the last 4
  lines survived.

## Evidence for the cause

1. **The error itself.** The frame is the `compile(...)` call inside `ast.parse`. pytest uses `ast.parse` when it
   rewrites test modules and when it formats a failed test's traceback. Collection had finished, because 43 tests had
   run, so it was most likely formatting a failure. A `MemoryError` there ends the whole session, which is why only 43
   tests ran.
2. **Windows diagnosed low memory during the run.** System log, Resource-Exhaustion-Detector event 2004 at 21:12:41 UTC
   (22:12:41 local), 10 seconds before the run ended: *"Windows successfully diagnosed a low virtual memory
   condition."* The largest users were GoogleDriveFS.exe at 29.2 GB, vmmemWSL (Docker's VM, which hosts PostgreSQL)
   at 7.8 GB, and claude.exe at 1.7 GB. The commit limit is 47.5 GB. The same event came again at 21:21:46 and
   21:54:10 UTC, and on no other day in the last three.
3. **The same code passed in CI.** The API code at `a7e611d` is identical to PR #192's head `262ef83`
   (`git diff a7e611d 262ef83 -- apps/api` is empty). CI run 38640559725 ran the full suite on that head and passed.
4. **The same tests pass alone now.** Rerun at 2026-10-14 23:20 UTC on `25bbafd`, which differs from `a7e611d` in the
   API only by the turnaround relabel (`review.py`, `review_router.py`, `test_review_demand.py`). It used the same 43
   node IDs in the same order (the first 43 collected: `test_academic_overview.py` through
   `test_attempts.py::test_deadline_tolerance_and_late_writes`) and the same test database. Result: **43 passed, 0
   failed, 0 errors in 57.2 s**, with a junit report kept. Free memory was 1.6 GB, with 21.1 of 47.5 GB committed.
   GoogleDriveFS was then using 1.45 GB.

## What is not known

- **The 7 failures.** Their names and tracebacks were cut off by `tail -4`, so they can't be shown, and these runs
  can't rule out a real fault that appears only under memory pressure. What they do show: the session crashed on
  memory, the operating system recorded memory exhaustion at that moment, the same code passed the full suite in CI,
  and the same tests pass in the same order now.
- **Nothing was shown to be a product defect.** No change to product code was made because of this run.

## Changes to how local suites are run

- No suite output goes through `tail` without `set -o pipefail`. Every full run writes `--junitxml` to the scratchpad,
  so failure names survive.
- Before a full local run, record free memory and committed memory. If committed memory is near the limit, rely on CI
  for the full suite and run only targeted files locally.
- A local timeout or crash is reported as unfinished, never as a pass.
- This is noted in the user's memory file `api-test-suite-quirks`.

## Separate environment change the same evening

After Docker Desktop restarted, Windows had reserved TCP 57353-57452, so the dev PostgreSQL could no longer bind 57432.
Port 55432, the default in `infra/docker-compose.yml`, was free again. The container was recreated from the committed
compose file on 55432, keeping the same `pgdata` volume and all databases. No owner configuration was changed.
