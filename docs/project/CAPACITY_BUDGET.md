# Capacity budget (P01.S4.T4, BUDGET-01)

**Status: planning numbers, not measurements.** The funded server or pooler limit, autoscaling maxima and measured
envelopes arrive with hosting (B03) and the load qualification (P20; AC50 and AC63). Nothing here is a performance
claim.

## Database connections (§5.8)

The sheet is code: `apps/api/src/portal_api/budget.py`. Print it with `uv run portal-budget`. Set
`PORTAL_DB_SERVER_CONNECTIONS` to the funded capacity to check the fit. `tests/test_budget.py` keeps it honest: the
totals match §5.8, and every installed database command belongs to a class.

| Class | Processes | Pool each | Total | Runs |
|---|---|---|---|---|
| api | 20 | 10 | 200 | API replicas; request work in a bounded threadpool |
| critical | 4 | 5 | 20 | `portal-expire-attempts`, `portal-mcq-regrade`, `portal-notification-worker` |
| standard | 4 | 3 | 12 | `portal-notification-trial-reminders` |
| bulk | 2 | 3 | 6 | `portal-export-worker`, `portal-import-worker`, `portal-import-reconcile`, `portal-asset-retention`, `portal-upload-reconcile`, `portal-help-import` |
| reserve | 1 | 7 | 7 | migrations, `portal-import-catalogue`, `portal-grant-role`, monitoring |
| written.ingestion | 2 | 3 | 6 | `portal-written-previews`, `portal-written-sweep-orphans` |
| written.reading | 4 | 2 | 8 | `portal-written-learner-deadlines`, `portal-written-repair` |
| written.assessment | 4 | 2 | 8 | `portal-written-auto-worker` (disabled until B10) |
| written.regrade | 1 | 2 | 2 | `portal-written-worker` |

- **Totals:** core 245, plus written 24, gives 269 planned connections.
- **Rolling-deploy overlap:** 2 extra API replicas, budgeted explicitly (+20), for a **peak of 289**.
- **Per-process pools (enforced since POOL-CAPS-01, P17.S2.T2):** every installed command is declared with `budget.process_class(...)`, which caps its process's pool at its row's "Pool each" before the first connection opens. `PORTAL_DB_POOL_SIZE` can only lower it (the API keeps the default of 10). `tests/test_pool_caps.py` fails if a command in `ENTRY_POINTS` lacks the declaration or names another class.
- **Bulk work pauses in mock windows:** the import and export workers claim no new work from 15 minutes before a scheduled mock window opens until 15 minutes after it closes, and the scheduled bulk jobs (`portal-asset-retention`, `portal-upload-reconcile`, `portal-import-reconcile --apply`) skip that run. Operator-run commands (`portal-help-import`) are not paused. `PORTAL_BULK_PAUSE_IN_MOCK_WINDOWS=false` turns the pause off. CPU and memory caps per class belong to the deployment (B03).
- **No overflow in production:** production refuses `db_max_overflow > 0` (config validator), so a pool size is a hard ceiling.
- **Pool saturation:** a request that can't get a connection within 5 s is answered `503 SERVICE_BUSY` with `Retry-After: 5`, never a hang (REL-02).
- **Written ingestion:** inside API requests it parses files in an isolated worker pool that holds no database connection (DBHOLD-01). The `written.ingestion` class covers the scheduled ingestion commands.

## Client traffic: what the apps do today

These rules come from the code (`attempt-runner.tsx` on the web, `app/attempt/[id].tsx` on mobile), not from a load test.

- **No periodic polling.** Each start or save response carries the server time. The clock runs locally from that offset, and the client never re-fetches the full attempt on a timer. The optional §5.8 clock check (a 60 to 72 s sampled interval, one in flight) is **not implemented**; nothing calls it.
- **Answer saves.** Changes are debounced by 400 ms and sent in order, with one save in flight. Before the deadline the client pre-flushes at D − 5 s.
- **Failed saves** are retried with exponential backoff:
  - delays start at 2 s and double, capped at 15 s, plus 0 to 0.5 s of jitter;
  - an `online` event (web) or the app returning to the foreground (mobile) flushes at once;
  - another device holding the attempt stops automatic retries (HANDOFF-01).
- **Offline progress queue** (OFFLINE-SYNC-01): completions and notes are sent once on sign-in and when the app returns to the foreground. They are not retried in a loop.

### Average versus peaks (§5.8)

- **Steady average:** with no periodic probe, periodic clock traffic is zero. If the optional probe is ever added, 2,000 continuously eligible clients at a 66 s mean interval give about 30 requests per second. That is an average, not a peak.
- **Save traffic** follows answer changes. Debouncing caps it at about 2.5 saves per second per actively answering learner (one per 400 ms), and real answering is far slower; the real-data spike measurement belongs to P20.
- **Retry amplification:**
  - A client whose saves fail sends at most one retry per backoff step: at 2, 4, 8 and 15 s, then every 15 s while it stays offline.
  - If N clients lose the network together, their retries spread over the jitter, but **a shared reconnect is synchronized**: every waiting client flushes on the `online` event at the same moment. That burst is about N saves within a fraction of a second.
  - §5.8 allows saves to bypass the recovery-probe limits, so this is permitted, but it is the envelope P20 must measure (school Wi-Fi restored). Adding 0 to 1 s jitter to the reconnect flush is a cheap mitigation if the measurement asks for it.
- **Starts and submissions** are separate envelopes, sized by AC50 (5,000 starts, and later 5,000 submissions, over separate 60 s windows).

## Admission control

- **Per account:** limits apply to support messages, help screenshots and staff import previews (P15.S4.T2), not to schools or carrier IPs.
- **Overload:** the API protects itself by pool timeout with `Retry-After`. Evidence parsing (`WorkersBusy`, `Retry-After: 10`) and teacher-review capacity refuse new work before accepting work they can't finish.
- **Not built yet:** per-endpoint admission budgets that shed catalogue, search and analytics first, then starts and probes, while protecting saves and submissions. They need the measured envelope (P20) and hosting (B03).

## Payload budgets

Web: compressed JavaScript per route is held under 180 KB in CI (PERF-01, `e2e/payload-budget.spec.ts`). Font, question
and API payload budgets, and the mobile startup budget, are measured with named devices (B09) in P20.
