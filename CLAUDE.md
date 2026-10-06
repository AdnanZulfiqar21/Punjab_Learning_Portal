# Repository instructions

Punjab Learning Portal: Class XI/XII (Punjab) Biology, Chemistry, Physics, Computer Science and Mathematics. Student web, Android, iOS and staff admin share one FastAPI backend.

- **Plan:** `Road Map/Punjab_Learning_Portal_Master_Roadmap_v2.2_Integrated_Written_Assessment.md`. Execute by its Section 18 dependency order.
- **Execution records:** `docs/project/` (IMPLEMENTATION_REGISTER, RESUME_STATE, DECISIONS, BLOCKERS, DEPENDENCIES, RELEASE_CHECKLIST, LAUNCH_MANIFEST, STACK). Update them with every meaningful change. Task state and gate state stay separate; a blocker is never passing evidence.
- **Academic sources:** `11 Class Data/`, `12 Class Data/` are the owner's originals. They are read-only and never committed (this repo is public; decision IMPL-01). Navigation indexes live in `education_knowledge/` (start at `Academic_Library_Index_Manifest.md`). Class XI and XII are never mixed. The derived catalogue is `content/` (`python content/tools/build_catalogue.py`).
- **No invented academic content.** No demo lessons, placeholder MCQs, fake marks or hard-coded success states. Generated drafts are labelled drafts and need a second-person review before publication.
- **Web (`apps/web`):** Next.js 16.4 with Cache Components. Read `apps/web/AGENTS.md` and `node_modules/next/dist/docs` before writing Next code. Data is fetched at request time from the API (runtime origin), never at build time.
- **API (`apps/api`):** `uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest` (needs `infra/docker-compose.yml` Postgres). Migrations run as a separate release step (`alembic upgrade head`), never on startup.
- **Contracts:** after API schema changes run `uv run python -m portal_api.export_openapi ../../packages/contracts/openapi.json` and `pnpm --filter @portal/contracts generate`. CI fails on drift.
- **Local ports:** API 8100, web 3100, Postgres 55432 (8000/3000 belong to another project on this machine).
