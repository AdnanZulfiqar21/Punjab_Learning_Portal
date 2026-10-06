# DEPENDENCIES (instantiates roadmap §18; P00.S3.T4)

Waves form a DAG; a later wave never claims an earlier gate. "Can start" means its prerequisite contracts exist, not that the earlier gate PASSED.

| Wave | Outcome | Prerequisites | Current state (2026-10-06) |
|---|---|---|---|
| A | Scope and planning contracts (P00.S1–S2, initial P00.S3, W00.S1, W01 schema, W02.S1–S2 design) | Owner requirements | IN_PROGRESS: scope (SCOPE-01), controls, decisions recorded |
| B | Source/permission intake (P22.S1, W00.S2.T1–T3) | A + supplied sources | IN_PROGRESS: 10 sources registered with checksums and indexes. Rights confirmation and named reviewers missing (B01) |
| C | Candidate provider processing approval (W00.S2.T4) | B | BLOCKED_EXTERNAL (B10) |
| D | Domain/client contracts (P01.S1–S3, P02.S1–S2, W01, W02.S1–S2) | A/B | IN_PROGRESS: curriculum/source model and API first |
| E | Foundation & shells (P03.S1–S3; minimum identity/data/storage; web/native shells) | B/D | IN_PROGRESS |
| F | Reviewed pilot content (P22.S2 RCS) | B/D + reviewers | BLOCKED_EXTERNAL (B01) for approval; drafting tooling can proceed |
| G | Empirical spikes (P01.S4, W02.S3) → estimates (P00.S3.T3) | C, E/F | TODO (P01.S4.T2 rendering spike can use real source figures now) |
| H | Core real-content vertical slice (P03.S4 …) | E/F/G | Catalogue/navigation slice on real indexed data can start; lesson/MCQ slice needs reviewed content (B01) |
| I–T | Written domain, commerce, qualification, readiness, rollout | per roadmap §18.1 | TODO |

## Critical path to Platform Ready
Reviewers (B01) → RCS production (P22.S2) → vertical slice on reviewed content → P04–P16 → P17–P20 qualification (needs B03, B07, B09) → P21.

## External lead times
See BLOCKERS.md. Cloud, store and merchant onboarding typically take days to weeks. Android recall approval duration is unknown.
