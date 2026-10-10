# Result shows "scoring pending"

**Owner:** platform operator.
**Rehearsal:** `apps/api/tests/test_scoring_recovery.py::test_a_scoring_failure_leaves_a_durable_submission_that_is_scored_later`.

## What it means

The learner's submission succeeded: the attempt is finalised and its receipt and answers are saved. Scoring failed or
was interrupted, so the result page says the result is being prepared (`SCORING_PENDING`). Nothing is lost.

## What happens automatically

The attempt worker (`portal-expire-attempts`, scheduled every few seconds) scores pending attempts under the attempt
lock, exactly once, then updates the mistake notebook. An `attempt.scoring_pending` audit record shows each failure,
and `attempt.scored_late` each recovery.

## When it doesn't clear

1. Check the API logs for the attempt ID (`scoring failed for attempt …`) to find the cause, for example a question
   version that can no longer be read.
2. Fix the cause, then let the worker run again. Never edit scores by hand. If a question itself is wrong, follow
   [disputed-question.md](disputed-question.md).
3. Tell the learner their answers were saved and when to expect the result.
