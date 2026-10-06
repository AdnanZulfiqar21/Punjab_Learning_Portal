# Punjab Learning Portal

Learning and assessment platform for Punjab **Class XI and Class XII**: Biology, Chemistry, Physics, Computer Science and Mathematics. It serves student web, Android and iOS clients plus a staff admin, all on one authoritative backend.

**Status:** early implementation (foundation and catalogue slice). Not ready for students. See `docs/project/RELEASE_CHECKLIST.md`.

| Path | What |
|---|---|
| `apps/api` | FastAPI backend (modular monolith, PostgreSQL, Alembic) |
| `apps/web` | Next.js student web app |
| `packages/contracts` | API contract (OpenAPI) and generated TypeScript types |
| `content/` | Source registry (checksums) and curriculum catalogue derived from the textbook indexes |
| `education_knowledge/` | Per-book, subject, visual and assessment indexes of the Class XI/XII textbooks |
| `infra/` | Local development services |
| `docs/project/` | Decisions, blockers, dependencies, implementation register, resume state |
| `Road Map/` | Master roadmap v2.2 (the plan) |

The owner's textbook PDFs are **not** in this repository. They are registered by checksum only (`docs/project/DECISIONS.md`, IMPL-01).

Quick start: see `docs/project/RESUME_STATE.md`.
