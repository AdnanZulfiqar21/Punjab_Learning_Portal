# Compromised account or leaked secret

**Owner:** owner/administrator (account actions); platform operator (secrets).
**Rehearsal:** `apps/api/tests/test_account_suspension.py::test_suspension_is_immediate_scoped_and_reversible`.

## A learner or staff account is compromised

1. **Suspend it now:** `POST /v1/admin/users/{id}/suspend` with a reason (administrator, MFA). This:
   - revokes every application session of that account at once;
   - makes the API refuse that account's identity tokens until reinstated;
   - leaves its data alone and never touches anyone else's attempts, uploads or results.
   You can't suspend your own account; ask another administrator.
2. **If it is a staff account,** also revoke its role grants (`/v1/admin/role-grants/{id}/revoke`) and review the
   audit trail (**Admin → Audit trail**, filter by the account) for what it did since the suspected time.
3. **Reset the credential at the identity provider** (password, MFA factor). The portal never stores production
   passwords.
4. **Reinstate** with `POST /v1/admin/users/{id}/reinstate` and a reason once the person has secured the account.
   Their attempts kept running on server time while suspended; a test whose deadline passed was finalised at its
   cutoff with every saved answer.

## A configuration secret leaked

| Secret | Rotate by | Side effects to plan for |
|---|---|---|
| Database password | New credential in the secret store, restart API and workers | Brief reconnects; no data change |
| OIDC client settings | Rotate at the identity provider, update `PORTAL_OIDC_*` | Tokens signed with revoked keys stop verifying; users sign in again |
| `PORTAL_TRIAL_REF_PEPPER` | New value in the secret store | Installation references hash differently: devices are not recognised as previously used. Decide with the owner whether to keep the old pepper for lookups during a transition (not built) |
| Object storage keys (B03) | Rotate at the provider | Uploads and downloads fail until workers restart |
| Email/SMS/push provider keys (B04/B07) | Rotate at the provider | Deliveries retry with backoff; nothing is lost |

After any rotation: run `python -m portal_api.release manifest` on the running build to record what is deployed,
check `/v1/ops/signals`, and record the incident.

Rotation itself depends on the hosting secret store (B03); this table is the plan, not yet a rehearsed procedure.
