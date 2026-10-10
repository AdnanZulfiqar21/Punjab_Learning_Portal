# Alert signals (P17.S3.T1, OPS-01)

`GET /v1/ops/signals` reports each value below with its level (`ok`, `warn` or `alert`), its thresholds, owner and a
link to this page. It is available to platform operators with MFA. A deployment's monitoring polls it, or runs the same
queries, and pages the owner on `alert`. Real paging and dashboards need the hosting decision (B03).

When an optional feature is broken, turn it off from `PUT /v1/ops/features/{key}` with a reason; the change is
audited. Switching a feature off refuses only new work, with 503 `FEATURE_DISABLED`. Active attempts, submissions,
marking, results and entitlements are never behind a switch. The keys are:

- `content_imports`
- `content_exports`
- `prompt_packages`
- `support_screenshots`
- `new_practice_tests`
- `new_written_tests`

## notification-backlog
**Signals:** `notification_queue_age_s` (warn 15 min, alert 1 h); `notification_dead_letters` (warn 1, alert 25).
**Owner:** platform operator.

1. Check that `portal-notification-worker` is running.
2. Read the dead letters (`GET /v1/ops/notifications/dead-letters`).
   - If they show a provider outage, wait for recovery and requeue.
   - If an address is invalid, suppress it.
3. In-app notices are never lost: only email and push deliveries queue.

## regrade-backlog
**Signals:** `written_regrade_queue_age_s` (warn 30 min, alert 2 h); `written_regrade_failed_jobs` (alert at 1).
**Owner:** academic operations, with the platform operator.

1. Check that `portal-written-worker` is running.
2. A failed job lists its failed scripts. Fix the cause, then an adjudicator uses **Retry** (MFA).
3. Released results stay as they are until the regrade succeeds.

## auto-assessment
**Signal:** `auto_assessment_dead_letters`.
**Owner:** platform operator.

- Automatic assessment is disabled while B10 is blocked. Any non-zero value outside development is unexpected.
- Inspect and requeue at `/v1/ops/written/auto-assessments`.

## marking-backlog
**Signals:** `marking_overdue_cases` (warn 1, alert 10); `marking_oldest_queued_age_s` (warn 2 days, alert 5 days).
**Owner:** academic operations.

1. Add markers in scope.
2. Lower admission capacity for the scope, so new written tests are refused honestly rather than accepted late.
3. Missed obligations follow the published remedy rules (allowance credit).

## support-backlog
**Signals:** `support_oldest_open_age_s` (warn 1 day, alert 3 days); `support_escalated_open` (warn 1, alert 10).
**Owner:** support lead.

Work the queue escalated-first. See the incident runbooks in this folder.

## pool-saturation
**Signal:** `db_pool_in_use_ratio` for this process (warn 0.7, alert 0.9).
**Owner:** platform operator.

- Saturated requests are answered 503 rather than queued (REL-02).
- Check for slow queries and stuck workers before adding capacity.
- Stay inside the connection budget (§5.8).

## error-rate
**Signal:** `http_server_error_ratio_5m`: share of this process's requests in the last five minutes answered 5xx (warn 1%, alert 5%).
**Owner:** platform operator.

- Find the failing route templates in the request logs (they carry the correlation ID; see P03.S4.T2).
- A 503 from pool saturation counts here too: check `db_pool_in_use_ratio` first.
- If one optional feature is failing, switch it off (Operations → feature switches) with a reason; active attempts and submissions are never behind a switch.

## latency
**Signal:** `http_latency_p95_ms_5m`: 95th-percentile request time for this process over five minutes (warn 800 ms, alert 2 s).
**Owner:** platform operator.

- Compare with `db_pool_in_use_ratio` and the queue-age signals; slow queries and stuck workers come before adding capacity.
- The budgets are initial engineering defaults until load evidence exists (B03); don't treat them as validated SLOs.

## submission-failures
**Signal:** `submission_server_error_ratio_5m`: share of final submissions (MCQ submit, written seal) answered 5xx (warn 0.1%, alert 1%).
**Owner:** platform operator.

- Treat any alert as urgent: a learner's work may be at risk. Submissions are idempotent, so a learner can retry safely.
- Check the attempt protocol logs by correlation ID, and follow `interrupted-mock.md` if a scheduled mock is running.
- A 409 (late, already submitted, refused) is a decision, not a failure, and is not counted.

## video-failures
**Signal:** `video_playback_failure_ratio`: unavailable until a media provider and reviewed videos exist (B05).
**Owner:** platform operator.

No video is served yet. When B05 is resolved, measure playback start failures from the provider's analytics and the player's error events, and add thresholds here.

## device-journey-budgets
**Signal:** `device_journey_budget_breaches`: unavailable until named reference devices exist (B09; builds B07).
**Owner:** platform operator.

Expo web is not device evidence. When B09 is resolved, run the P02.S4.T1 journeys on the reference devices and report breaches here.
