# Disputed question (soft, then void quarantine)

**Owner:** subject reviewer (report triage), publisher (quarantine), academic adjudicator (score correction).
**Rehearsal:** `apps/api/tests/test_mcq_corrections.py::test_rehearsal_disputed_question_soft_then_void`.

## Steps

1. **Report arrives.** A learner reports a question from their result. The request reaches reviewers of that
   class and subject. It carries the exact question version and does not identify the learner.
2. **Suspected defect → SOFT quarantine.** A publisher (MFA) quarantines the item at level `SOFT` with a reason
   citing the request (**Studio → item → Quarantine**).
   - The question version leaves new practice forms at once.
   - Existing forms, open attempts and released scores stay as they are. Do not tell learners their score will change.
3. **Review.** The subject reviewer checks the question against the approved source.
   - **Not a defect:** release the quarantine with a reason (**Release from quarantine**), then reply and resolve.
   - **Confirmed, no valid answer:** change the level to `VOID` (**Change quarantine level**). This does not return
     the question to learners. Then an academic adjudicator (MFA) chooses **Record void and re-score**, with a reason
     of at least 10 characters.
   - **Confirmed, wrong key:** change the level to `KEY_ERROR`. The adjudicator picks the corrected answer and
     chooses **Record key correction and re-score**.
4. **What happens on re-score.** Every submitted attempt that contains this question version gets a new score version:
   - VOID: the form's pinned treatment applies. For practice that is EXCLUDE, which removes the question from both
     marks and maximum.
   - KEY_ERROR: the attempt is marked against the corrected key.

   Each affected learner gets one "result updated" notice. Their result shows the revision note, and earlier marks
   stay in their history. Tests still open get the correction when they are submitted.
5. **Re-classifying.** A VOID can become KEY_ERROR, or the reverse, by changing the level and recording a new
   correction. The new correction supersedes the old one explicitly. A corrected question cannot go back to SOFT or
   be released. Publish a corrected version instead.
6. **Tell the reporter.** Resolve the request. Internal notes are never shown.

If a re-score was interrupted, an operator runs `portal-mcq-regrade`. It is safe to repeat.

## Audit trail

The audit log records:

- `content.quarantined` and `content.quarantine_level_changed`, with the level and reason;
- `assessment.score_correction_recorded`, with the defect, version, any corrected key, what it supersedes, and the reason;
- `attempt.rescored` for each new score version.
