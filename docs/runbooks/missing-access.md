# Learner paid but has no access

**Owner:** support (first line), finance (remedy). **Rehearsal:** `test_rehearsal_missing_paid_access`.

**Status:** online payments are not live (blocker B06). Until they are, there is no payment record to reconcile, so the
remedy is an interim, time-limited grant. When payments go live, this runbook must add "find the payment and
re-deliver its entitlement" before any manual grant.

## Steps

1. **Open the request.** In **Support queue**, open the learner's access request. Ask for evidence of payment if none
   is attached, such as the receipt reference. Do not ask for card numbers.
2. **Check the account.** In **Find a learner**, enter their exact email. In the timeline, confirm:
   - there is no `Access granted` entry for the period they paid for;
   - whether a free trial is active or used.
3. **Escalate to finance.** On the request, choose **Escalate**. The reason should say what evidence you saw. This is
   a staff note; the learner never sees it.
4. **Finance grants interim access.** Use `POST /v1/admin/entitlements`. This needs finance or owner-admin, plus MFA.
   - Source: `promotional`.
   - Duration: up to 7 days while payment is verified.
   - Reason: must cite the request ID.
5. **Confirm and resolve.** Reload the timeline and check that `Access granted` appears. Reply to the learner and set
   the request to **Resolved**. The learner gets one "request resolved" notice.
6. **If payment is not confirmed** by the end of the grant, finance revokes it with a reason
   (`POST /v1/admin/entitlements/{id}/revoke`). Revocations are recorded, never deleted.

## Audit trail

The following are all recorded in the audit log:

- the `support.lookup` and `support.timeline_viewed` steps;
- `support.escalated` on the request;
- `entitlement.granted` on the learner, with the actor and reason.
