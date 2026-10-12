"""P19.S3.T1 (MIGRATION-COMPAT-01): an upgrade keeps working for what is already out there.

1. **Oldest supported mobile client.** `compat/mobile_2026-10-10.json` holds every operation the mobile app at commit
   `362db5b` calls, with the request and response schemas it was built against (generated from that commit). The
   current API must still serve each one: same method and path, no new required input, every field the old app reads
   still present with the same type, and never null where it wasn't.
2. **Rollback without erasing data.** Rolling back means running the previous build against the current schema (a
   release never runs `alembic downgrade` on data). So every table and column the previous build knows still exists
   with the same type, and anything added since can be left out by the previous build's inserts (nullable or
   defaulted), so new purchases, attempts and other rows written after the upgrade stay where they are.
3. **A populated earlier schema upgrades without loss.** `compat/baseline_2026-10-10.sql.gz` is data written by the
   `362db5b` build itself (its own test journeys: learners, sessions, trials and device claims, practice and mock
   attempts, written attempts and marking, notebooks, support, notifications, exports, privacy requests, studio
   items). It is loaded at that build's schema and upgraded to head; every row survives, the current models read all
   of it, and the current API signs its learners in and serves their attempts, results and progress. Technical
   fixtures only: no real people, no academic content beyond the public catalogue and source registry.

Moving the baseline to a newer release (docs/runbooks/release-rollback.md): check that commit out in a worktree, run
a cross-section of its own API tests against an empty `*_test` database (its conftest migrates and leaves the data),
dump with `pg_dump --data-only --column-inserts --exclude-table=alembic_version`, drop the psql `\\restrict` lines,
gzip it here, extract its mobile app's calls and schemas into `compat/mobile_<date>.json`, and update
`BASELINE_REVISION`.
"""

from __future__ import annotations

import copy
import gzip
import json
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from portal_api.db import Base
from portal_api.main import app

COMPAT = Path(__file__).parent / "compat"
API_DIR = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "e8b2d6f4a193"  # build 362db5b (2026-10-10); a revision id  # pragma: allowlist secret
MOBILE = json.loads((COMPAT / "mobile_2026-10-10.json").read_text(encoding="utf8"))


# ------------------------------------------------------------------ 1. the oldest supported mobile client
class _Contract:
    def __init__(self, old_schemas: dict[str, Any], new_schemas: dict[str, Any]) -> None:
        self.old, self.new = old_schemas, new_schemas
        self.problems: list[str] = []
        self._seen: set[tuple[str, str, str]] = set()

    @staticmethod
    def _resolve(node: dict[str, Any], schemas: dict[str, Any]) -> tuple[dict[str, Any], str]:
        name = ""
        while "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            node = schemas[name]
        return node, name

    def _norm(self, node: dict[str, Any], schemas: dict[str, Any]) -> tuple[dict[str, Any], bool, str]:
        node, name = self._resolve(node, schemas)
        nullable = False
        for key in ("anyOf", "oneOf"):
            if key in node:
                options = [o for o in node[key] if o.get("type") != "null"]
                nullable = len(options) < len(node[key])
                if len(options) == 1:
                    inner, inner_name = self._resolve(options[0], schemas)
                    return inner, nullable, inner_name or name
                return {key: options}, nullable, name
        if "allOf" in node and len(node["allOf"]) == 1:
            inner, inner_name = self._resolve(node["allOf"][0], schemas)
            return inner, nullable, inner_name or name
        return node, nullable, name

    def compare(self, old: dict[str, Any], new: dict[str, Any], where: str, reading: bool) -> None:
        """`reading`: the old app reads this (a response); otherwise it sends it (a request)."""
        o, o_null, o_name = self._norm(old, self.old)
        n, n_null, n_name = self._norm(new, self.new)
        if o_name and n_name:
            key = (o_name, n_name, "r" if reading else "w")
            if key in self._seen:
                return
            self._seen.add(key)
        if reading and n_null and not o_null:
            self.problems.append(f"{where}: may now be null")
        if not reading and o_null and not n_null:
            self.problems.append(f"{where}: no longer accepts null")
        ot, nt = o.get("type"), n.get("type")
        if ot and nt and ot != nt and not (ot == "integer" and nt == "number" and not reading):
            self.problems.append(f"{where}: type {ot} became {nt}")
            return
        oe, ne = o.get("enum"), n.get("enum")
        if not reading and oe is not None and ne is not None and set(oe) - set(ne):
            self.problems.append(f"{where}: no longer accepts {sorted(set(oe) - set(ne))}")
        if reading and ne is not None and (oe is None or set(ne) - set(oe)):
            extra = sorted(set(ne) - set(oe or []))
            self.problems.append(f"{where}: may now send values the old app has never seen: {extra}")
        if "properties" in o or "properties" in n:
            op, np_ = o.get("properties", {}), n.get("properties", {})
            if reading:
                for prop, schema in op.items():
                    if prop not in np_:
                        self.problems.append(f"{where}.{prop}: removed")
                    else:
                        if prop in o.get("required", []) and prop not in n.get("required", []):
                            self.problems.append(f"{where}.{prop}: may now be missing")
                        self.compare(schema, np_[prop], f"{where}.{prop}", reading)
            else:
                for prop in n.get("required", []):
                    if prop not in op:
                        self.problems.append(f"{where}.{prop}: newly required")
                for prop, schema in op.items():
                    if prop in np_:
                        self.compare(schema, np_[prop], f"{where}.{prop}", reading)
                    elif n.get("additionalProperties") is False:
                        self.problems.append(f"{where}.{prop}: now refused")
        if "items" in o and "items" in n:
            self.compare(o["items"], n["items"], f"{where}[]", reading)


def _json_schema(body: dict[str, Any] | None) -> dict[str, Any] | None:
    if not body:
        return None
    content = body.get("content", {})
    media = content.get("application/json")
    return media.get("schema") if media else None


def _mobile_problems(spec: dict[str, Any]) -> list[str]:
    contract = _Contract(MOBILE["schemas"], spec["components"]["schemas"])
    for op in MOBILE["operations"]:
        method, path = op["method"], op["path"]
        where = f"{method.upper()} {path}"
        current = spec["paths"].get(path, {}).get(method)
        if current is None:
            contract.problems.append(f"{where}: removed")
            continue
        old_params = {(p["in"], p["name"]) for p in op["parameters"]}
        for p in current.get("parameters", []):
            if p.get("required") and (p["in"], p["name"]) not in old_params:
                contract.problems.append(f"{where}: new required {p['in']} parameter {p['name']}")
        old_body, new_body = op["requestBody"], current.get("requestBody")
        if new_body and new_body.get("required") and not old_body:
            contract.problems.append(f"{where}: now needs a request body")
        if old_body and new_body:
            for media in old_body.get("content", {}):
                if media not in new_body.get("content", {}):
                    contract.problems.append(f"{where}: no longer accepts {media}")
            old_schema, new_schema = _json_schema(old_body), _json_schema(new_body)
            if old_schema and new_schema:
                contract.compare(old_schema, new_schema, f"{where} body", reading=False)
        new_ok = {k: v for k, v in current.get("responses", {}).items() if k.startswith("2")}
        for status, response in op["responses"].items():
            old_schema = _json_schema(response)
            if old_schema is None:
                continue  # the old app reads no body here
            match = new_ok.get(status) or next((r for r in new_ok.values() if _json_schema(r)), None)
            new_schema = _json_schema(match)
            if new_schema is None:
                contract.problems.append(f"{where}: no longer returns a body")
                continue
            contract.compare(old_schema, new_schema, f"{where} -> {status}", reading=True)
    return contract.problems


def test_the_oldest_supported_mobile_client_still_works() -> None:
    problems = _mobile_problems(app.openapi())
    assert problems == [], "\n".join(problems)


def test_the_client_check_catches_breaking_changes() -> None:
    spec = copy.deepcopy(app.openapi())
    schemas = spec["components"]["schemas"]
    me = schemas["MeOut"]
    me["properties"].pop("email")  # a field the old app reads disappears
    me["properties"]["id"] = {"anyOf": [{"type": "string"}, {"type": "null"}]}  # and one may now be null
    submit = schemas["portal_api__modules__assessment__schemas__SubmitIn"]
    submit["properties"]["new_field"] = {"type": "string"}
    submit["required"] = [*submit.get("required", []), "new_field"]  # an input the old app never sends
    spec["paths"]["/v1/practice/availability"]["get"]["parameters"].append(
        {"name": "region", "in": "query", "required": True, "schema": {"type": "string"}}
    )
    del spec["paths"]["/v1/me/notebook"]["get"]
    problems = "\n".join(_mobile_problems(spec))
    for expected in (
        "GET /v1/me -> 200.email: removed",
        "GET /v1/me -> 200.id: may now be null",
        "POST /v1/attempts/{attempt_id}/submit body.new_field: newly required",
        "GET /v1/practice/availability: new required query parameter region",
        "GET /v1/me/notebook: removed",
    ):
        assert expected in problems, (expected, problems)


# ------------------------------------------------------------------ scratch databases
def _server_url() -> str:
    return os.environ["PORTAL_DATABASE_URL"].rsplit("/", 1)[0]


@contextmanager
def _scratch(tag: str) -> Iterator[str]:
    name = f"portal_{tag}_{uuid.uuid4().hex[:8]}_test"
    admin = create_engine(f"{_server_url()}/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield f"{_server_url()}/{name}"
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _run(url: str, *args: str) -> str:
    """Run in a fresh interpreter, so its settings and engines point at the scratch database only."""
    out = subprocess.run(  # noqa: S603 - this interpreter, fixed arguments
        [sys.executable, *args],
        cwd=API_DIR,
        env={**os.environ, "PORTAL_DATABASE_URL": url},
        capture_output=True,
        text=True,
        encoding="utf8",
        timeout=900,
    )
    assert out.returncode == 0, out.stdout[-2000:] + out.stderr[-4000:]
    return out.stdout


def _alembic(url: str, *args: str) -> str:
    return _run(url, "-m", "alembic", *args)


# ------------------------------------------------------------------ 2. rollback without erasing data
def _schema(engine: Engine) -> dict[str, dict[str, Any]]:
    insp = inspect(engine)
    tables: dict[str, dict[str, Any]] = {}
    for table in insp.get_table_names():
        if table == "alembic_version":
            continue
        tables[table] = {
            "columns": {
                c["name"]: {
                    "type": str(c["type"]),
                    "nullable": c["nullable"],
                    "default": c.get("default") or (c.get("identity") and "identity"),
                }
                for c in insp.get_columns(table)
            },
            "unique": {tuple(u["column_names"]) for u in insp.get_unique_constraints(table)}
            | {tuple(i["column_names"]) for i in insp.get_indexes(table) if i["unique"]},
            "checks": {c["name"]: c["sqltext"] for c in insp.get_check_constraints(table)},
        }
    return tables


def _allowed(check: str) -> set[str]:
    """The values a `column = ANY (ARRAY[...])` check allows; a widened list stays compatible."""
    values = set(re.findall(r"'([^']*)'::", check))
    return values if "ANY (ARRAY[" in check else {check}


def test_the_previous_build_runs_on_the_current_schema() -> None:
    with _scratch("previous") as previous_url, _scratch("head") as head_url:
        _alembic(previous_url, "upgrade", BASELINE_REVISION)
        _alembic(head_url, "upgrade", "head")
        previous_engine, head_engine = create_engine(previous_url), create_engine(head_url)
        previous, head = _schema(previous_engine), _schema(head_engine)
        previous_engine.dispose()
        head_engine.dispose()
    problems = []
    for table, old in previous.items():
        new = head.get(table)
        if new is None:
            problems.append(f"{table}: dropped")
            continue
        for column, info in old["columns"].items():
            now = new["columns"].get(column)
            if now is None:
                problems.append(f"{table}.{column}: dropped")
            elif now["type"] != info["type"]:
                problems.append(f"{table}.{column}: type {info['type']} became {now['type']}")
            elif info["nullable"] and not now["nullable"] and not now["default"]:
                problems.append(f"{table}.{column}: now NOT NULL without a default")
        for column, now in new["columns"].items():
            if column not in old["columns"] and not now["nullable"] and not now["default"]:
                problems.append(f"{table}.{column}: added NOT NULL without a default, so earlier inserts fail")
        for unique in new["unique"] - old["unique"]:
            problems.append(f"{table}: new unique rule on {unique}, which earlier writes may break")
        for name, check in new["checks"].items():
            before = old["checks"].get(name)
            if before is None:
                problems.append(f"{table}: new check {check}")
            elif before != check and not _allowed(before) <= _allowed(check):
                problems.append(f"{table}: check {name} narrowed to {check}")
    assert len(previous) > 50  # the comparison really covers the earlier schema
    assert problems == [], "\n".join(problems)


# ------------------------------------------------------------------ 3. a populated earlier schema upgrades
SERVE = """
import json, os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from portal_api.main import create_app

engine = create_engine(os.environ["PORTAL_DATABASE_URL"])
with engine.connect() as c:
    rows = c.execute(text(
        "select distinct on (u.id) u.email, a.id from attempt a join app_user u on u.id = a.user_id"
        " join dev_credential d on d.user_id = u.id join practice_form f on f.id = a.form_id"
        " where a.status <> 'active' and f.kind = 'practice' order by u.id, a.started_at limit 6"
    )).all()
engine.dispose()
out = []
with TestClient(create_app()) as client:
    for email, attempt_id in rows:
        token = client.post("/v1/dev-auth/token", json={"email": email, "password": "correct-horse-battery"})
        headers = {"Authorization": "Bearer " + token.json().get("access_token", "")}
        out.append({
            "token": token.status_code,
            "me": client.get("/v1/me", headers=headers).status_code,
            "access": client.get("/v1/me/access", headers=headers).status_code,
            "attempt": client.get(f"/v1/attempts/{attempt_id}", headers=headers).status_code,
            "result": client.get(f"/v1/attempts/{attempt_id}/result", headers=headers).status_code,
            "progress": client.get("/v1/me/progress", headers=headers).status_code,
        })
print(json.dumps(out))
"""


def _counts(engine: Engine) -> dict[str, int]:
    with engine.connect() as conn:
        tables = [t for t in inspect(conn).get_table_names() if t != "alembic_version"]
        return {t: int(conn.execute(text(f'select count(*) from "{t}"')).scalar_one()) for t in tables}  # noqa: S608 - reflected names


def test_a_populated_earlier_schema_upgrades_without_loss() -> None:
    dump = gzip.decompress((COMPAT / "baseline_2026-10-10.sql.gz").read_bytes()).decode("utf8")
    with _scratch("upgrade") as url:
        _alembic(url, "upgrade", BASELINE_REVISION)
        loader = create_engine(url, poolclass=NullPool)  # the dump changes session settings; don't pool them
        raw = loader.raw_connection()
        try:
            cur = raw.cursor()
            cur.execute("SET session_replication_role = replica")  # rows exactly as dumped; FKs held at the source
            cur.execute(dump)
            cur.close()
            raw.commit()
        finally:
            raw.close()
            loader.dispose()
        engine = create_engine(url, poolclass=NullPool)
        before = _counts(engine)
        assert before["app_user"] > 50 and before["attempt"] > 20  # really populated

        _alembic(url, "upgrade", "head")
        _alembic(url, "check")
        after = _counts(engine)
        assert {t: after[t] for t in before} == before  # every earlier row is still there

        with Session(engine) as db:  # the current models read every row: types, enum values, JSON
            for mapper in Base.registry.mappers:
                if mapper.local_table is not None and getattr(mapper.local_table, "name", None) in before:
                    db.scalars(select(mapper.class_)).all()
                    db.expunge_all()
        engine.dispose()

        served = json.loads(_run(url, "-c", SERVE).strip().splitlines()[-1])
    assert len(served) >= 3
    expected = {"token": 200, "me": 200, "access": 200, "attempt": 200, "result": 200, "progress": 200}
    assert all(row == expected for row in served), served
