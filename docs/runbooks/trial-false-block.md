# Trial refused on a shared or second-hand device

**Owner:** student operations (support role with trial review, MFA). **Rehearsal:** `test_rehearsal_trial_false_block_appeal`.

A used-device flag shows that the device was used before. It does not prove the current person is dishonest (roadmap
§16.7). Families share phones and phones are resold.

## Steps

1. **Open the request.** The learner's access request usually says "free trial refused" or "already used on this
   device".
2. **Read the decision.** In **Find a learner**, open the timeline. `Trial decision` entries show each claim state
   with its reason. For example, `CLOSED_INELIGIBLE` with the reason "prior promotional use recorded for this device".
   The timeline never shows device identifiers or provider evidence.
3. **Decide privately.** Ask for only what you need, such as a purchase receipt for a second-hand phone or a
   statement that the device is shared within the family. Never ask for CNIC, biometrics or card details.
4. **Issue an exception** if you accept the explanation. Use `POST /v1/staff/trial/exceptions` (MFA):
   - email: the learner's exact email;
   - surface: the device platform;
   - days: 1–30 (usually 7);
   - reason: must cite the request ID.

   The exception is account-scoped and time-bounded. It does **not** clear the device marker, reset program history
   or extend an existing trial.
5. **Ask the learner to try again.** Their next trial activation on that device succeeds:
   - with no trial yet, a new grant is made under the exception;
   - with an existing trial, the device is authorized under the exception.

   The timeline then shows `Trial exception granted`, `Free trial started` and `Trial device approved`.
6. **Resolve** the request with a short reply.

If you do not accept the explanation, reply politely and resolve the request. Paid access is never blocked by a trial
decision.

## Audit trail

The audit log records `trial.exception_granted` with the reviewer, surface, duration and reason. The claim's
decision trail says the grant was allowed by that exception.
