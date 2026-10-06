# STACK — pinned versions (P01.S1.T1)

Checked **2026-10-06/07** against the official registries (npm, PyPI, Docker Hub, GitHub releases). Exact versions are locked in `apps/api/uv.lock` and `pnpm-lock.yaml`. Upgrades follow the roadmap §6.4 requalification rule. "Latest" is never adopted automatically (IMPL-02).

| Layer | Component | Pinned | Notes |
|---|---|---|---|
| Runtime | Python | 3.13 (`>=3.13,<3.14`) | Supported stable line with wheels for all API deps |
| Runtime | Node.js | 22 LTS (local 22.23.2) | `engines` in root package.json |
| Package mgr | uv / pnpm | 0.12.23 / 10.34.6 | pnpm 12 exists; staying on the 10 line until a deliberate upgrade |
| API | FastAPI / Pydantic / pydantic-settings | 0.142.2 / 2.13.5 / 2.15.0 | |
| API | SQLAlchemy / Alembic / psycopg | 2.1.3 / 1.20.0 / 3.3.6 (binary) | `Result.tuples()` is deprecated in 2.1 and not used |
| API | Uvicorn | 0.54.0 (standard) | |
| API dev | pytest / httpx2 / ruff / mypy | 9.1.1 / 2.13.1 / 0.16.10 / 2.4.0 | Starlette's test client now uses httpx2 |
| Database | PostgreSQL | 17 (local `postgres:17-alpine`, 17.11) | 18 is available. 17 was chosen for broad managed-service support; final D14 at P17. Extension: `pg_trgm` |
| Cache / queue (local) | Valkey 8 / ElasticMQ (SQS-compatible) | images `valkey/valkey:8-alpine`, `softwaremill/elasticmq-native` | Development emulation only |
| Web | Next.js / React | 16.4.0 / 19.3.0 | App Router with **Cache Components and Partial Prefetching on**. Read `node_modules/next/dist/docs` before changing patterns (`apps/web/AGENTS.md`) |
| Web | TypeScript | 5.9.3 | TS 7.0.2 (native compiler) deferred until Next/ESLint compatibility is verified |
| Web | Tailwind CSS / @tailwindcss/turbopack | 4.3.3 / 4.3.3 | |
| Web | ESLint / eslint-config-next | 9.39.5 / 16.4.0 | ESLint 10 exists; the template pins 9 for compatibility |
| Web test | @playwright/test | 1.63.0 | Chromium; desktop + Pixel 7 projects |
| Contracts | openapi-typescript | 7.13.0 | `packages/contracts` generated from the API OpenAPI document |
| Mobile | Expo SDK / expo-router / React Native / React / TypeScript | 57.0.27 / 57.0.25 / 0.86.3 / 19.2.3 / ~6.0.3 | Versions are dictated by the SDK (use `npx expo install`); `expo-doctor` 21/21 passing. RN 0.87.1 exists but is not part of SDK 57. Read `apps/mobile/AGENTS.md` (versioned Expo docs) before changing patterns |
| CI | actions/checkout v7, setup-node v7, setup-python v7, pnpm/action-setup v6, astral-sh/setup-uv v10.2.0 (no floating major tag), upload-artifact v7 | | |

## Local ports
API `127.0.0.1:8100`, web `localhost:3100`, Expo web target `localhost:8190`, PostgreSQL `127.0.0.1:55432`, Valkey `56379`, queue `59324`. Ports 8000 and 3000 are used by another project on this machine.
