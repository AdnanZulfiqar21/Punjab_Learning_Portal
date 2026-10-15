# Emergency staff access

**Owner:** the person who can run commands on the deployment (break-glass). Afterwards, an owner administrator.
**Rehearsal:** `apps/api/tests/test_identity.py::test_the_bootstrap_command_is_audited_with_no_actor`.

Use this only when nobody can reach **Admin → Roles** — the first administrator has never been created, or the only
administrator is locked out. Do not edit the database.

## Grant the first administrator

1. The person must already have signed in once, so the account exists. The command matches the email exactly and
   refuses to guess when it finds none or more than one.
2. From the API directory, with the deployment's own configuration (not a laptop database):

   ```
   portal-grant-role --email owner@example.org --role owner_admin --reason "break-glass: the only administrator is locked out"
   ```

   A class-and-subject limit is `--grades 11 --subjects chemistry` when the grant should not cover everything.
3. The command writes a `role.grant` audit row with no actor and `via: cli`, including the role, scope and reason.
   Confirm it on **Admin → Audit trail** after signing in.
4. That person signs in with multi-factor authentication and makes every later grant and revocation through
   **Admin → Roles**. Those require MFA and name the actor. Do not use this command again while an administrator
   can sign in.

## After access is restored

Revoke the break-glass grant if it was wider than the person should keep (`/v1/admin/role-grants/{id}/revoke`, with
a reason). The grant and the audit row stay in the history.
