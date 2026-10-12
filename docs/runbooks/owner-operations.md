# Owner operations (P16.S4.T3, OWNER-VALIDATION-01)

These are the everyday operations an owner runs from the portal's own screens, without a database, a command line or a developer.

Every step:
- needs multi-factor sign-in;
- asks for a reason;
- is recorded in the audit log (**Account → Audit trail**).

Each operation is checked by an automated test that walks the same steps through the real API, with a different person and role at each handoff.

| Operation | Where | Who | Checked by |
| --- | --- | --- | --- |
| Add or remove staff | **Account → Staff**: email, role, classes and subjects (academic roles), reason | Owner or administrator. Nobody changes their own roles. | `apps/api/tests/test_owner_validation.py` |
| Confirm publication rights for a source | Studio → Sources | Owner | `tests/test_content_workflow.py` |
| Import, review and publish questions and lessons | Studio → Imports, Items | Author, then an independent reviewer, then a publisher | `tests/test_owner_operations.py` |
| Quarantine a question and record a score correction (regrade) | Studio → Item → Quarantine; Score corrections | Publisher, then a scoped academic adjudicator | `tests/test_owner_operations.py`, `tests/test_mcq_corrections.py` |
| Withdraw access (today's refund) | Admin → Entitlements (API), Business overview | Finance | `tests/test_owner_operations.py` |
| Suspend or reinstate an account | Admin (API) | Owner or administrator | `tests/test_owner_operations.py`, `tests/test_account_suspension.py` |
| Resolve a trial appeal | Support → Find a learner → Trial exception | Support with trial review | `tests/test_owner_operations.py`, [trial-false-block.md](trial-false-block.md) |
| Check a syllabus update | Studio → Sources (notices and source reviews) | A scoped subject reviewer decides; an author can only log the notice | `tests/test_owner_validation.py`, `tests/test_academic_updates.py` |
| Read the business, funnel, learning, economics and trial reports | **Account** links | Owner and finance | `tests/test_business_overview.py` and the report tests |

**Known gaps:**
- Withdrawing an entitlement and suspending an account have API routes and audited records, but no dedicated web form yet.
- Refunds through a payment provider don't exist until B06.

## What still needs an external specialist

These are not hidden behind buttons. The portal can't do them, and pretending otherwise would be unsafe.

| Needs | Why | Blocker |
| --- | --- | --- |
| Named subject reviewers and an academic production lead | Content is published only after independent academic review | B01 |
| Two people to verify official exam patterns | MDCAT/ECAT patterns must match the official notices | B02 |
| Cloud hosting, backups, restore and secret rotation | Running and recovering the service | B03 |
| Identity provider tenant, email and SMS senders | Real sign-in, recovery and messages | B04 |
| Video hosting provider | Lecture delivery and its costs | B05 |
| Payment provider and merchant agreement | Purchases, refunds and reconciliation | B06 |
| Apple and Google developer accounts, signing, store review | Installable apps, store billing, device checks | B07, B08 |
| Written-assessment processor approval and legal review | Any automatic reading of real scripts | B10 |
| Privacy notice and retention schedule (legal) | What is deleted, when, and what is kept | B15 |
| Independent security testing | Before launch | P18 |
| Brand and domain | Final names and addresses | B11 |
