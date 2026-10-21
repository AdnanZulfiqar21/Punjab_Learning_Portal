# API and worker image (P03.S3.T2). One image, different commands. It does not migrate on startup.
FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /uvx /bin/
WORKDIR /srv

COPY apps/api/pyproject.toml apps/api/uv.lock apps/api/alembic.ini ./
COPY apps/api/src ./src
COPY apps/api/migrations ./migrations

RUN uv sync --frozen --no-dev --no-editable
ENV PATH="/srv/.venv/bin:$PATH"

EXPOSE 8100
# A release runs `alembic upgrade head` as its own step, then starts this process or a worker command.
CMD ["uvicorn", "portal_api.main:app", "--host", "0.0.0.0", "--port", "8100"]
