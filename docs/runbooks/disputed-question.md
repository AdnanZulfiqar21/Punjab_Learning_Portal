# Disputed question (soft, then void quarantine)

**Owner:** subject reviewer (report triage), publisher (quarantine), academic adjudicator (scoring correction).
**Status:** soft quarantine works and is tested. **Void and key-error score propagation (roadmap §5.7) is not built
yet.** It is the next engineering task. Until it lands, do not tell learners their score will change.

## Steps

1. **Report arrives.** A learner reports a question from their result. The request reaches reviewers of that
   class and subject. It carries the exact question version and does not identify the learner.
2. **Suspected defect → SOFT quarantine.** A publisher (MFA) quarantines the item at level `SOFT` with a reason
   citing the request (**Studio → item → Quarantine**).
   - The question version leaves new practice forms at once.
   - Existing forms and attempts keep their original contents, and no score changes.
3. **Review.** The subject reviewer checks the question against the approved source.
   - **Not a defect:** release the quarantine with a reason (**Release**), then reply and resolve.
   - **Confirmed, no valid answer:** quarantine at `VOID`. The pinned invalid-item treatment (EXCLUDE for practice)
     must then be applied to existing scores as a new score version. *Not built yet.*
   - **Confirmed, wrong key:** quarantine at `KEY_ERROR`. An adjudicator records the corrected key, and existing
     attempts are re-scored as a new score version. *Not built yet.*
4. **Tell the reporter.** Resolving the request sends one "request resolved" notice. Internal notes are never shown.

## Audit trail

The audit log records `content.quarantined` and `content.released` with the actor, level and reason. The help request
holds the conversation.
