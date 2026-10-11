"""P18.S2.T2 (IMPORT-ABUSE-01): hostile import files fail as ordinary validation errors, never a server error, and in
bounded time; repeated previews are rate limited; nothing an import does becomes public. Technical fixture data."""

from __future__ import annotations

import json
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from portal_api.db import get_sessionmaker
from portal_api.modules.content import imports
from portal_api.modules.content.models import ContentItem
from tests.test_content_import import _author, _doc, _preview, _row, _setup

HEADER = "external_id,chapter,title,stem,option_a,option_b,correct\n"


def test_an_oversized_csv_field_is_a_validation_error(client: TestClient) -> None:
    who = _author(client)
    r = _preview(client, who, (HEADER + "x1,ch,T," + "a" * 300_000 + ",A,B,A\n").encode(), fmt="csv")
    assert r.status_code == 422 and r.json()["code_reason"] == "CSV", r.text


def test_deeply_nested_json_is_a_validation_error(client: TestClient) -> None:
    who = _author(client)
    deep = b'{"schema_version":1,"kind":"mcq","items":[' + b"[" * 200_000 + b"]" * 200_000 + b"]}"
    r = _preview(client, who, deep)
    assert r.status_code == 422 and r.json()["code_reason"] == "JSON", r.text
    nested_row = {"external_id": "n1", "title": "x", "body": {"stem": []}}
    cur: dict[str, Any] = nested_row["body"]  # type: ignore[assignment]
    for _ in range(900):  # depth json accepts but recursive validators might not
        cur["x"] = {}
        cur = cur["x"]
    r = _preview(client, who, json.dumps({"schema_version": 1, "kind": "mcq", "items": [nested_row]}).encode())
    assert r.status_code == 422 and r.json()["code_reason"] == "JSON", r.text


def test_nul_characters_are_rejected_not_stored(client: TestClient) -> None:
    who = _author(client)
    chapter, refs = _setup()
    r = _preview(client, who, _doc(_row("nul-1", chapter, refs, "Stem with a \u0000 NUL")))
    assert r.status_code == 422 and r.json()["code_reason"] == "ENCODING", r.text
    r = _preview(client, who, ("x1,ch,T,stem\x00,A,B,A\n").join([HEADER, ""]).encode(), fmt="csv")
    assert r.status_code == 422 and r.json()["code_reason"] == "ENCODING", r.text


def test_a_flood_of_tiny_rows_stops_at_the_row_limit_quickly() -> None:
    data = (HEADER + "a,b,c,d,e,f,g\n" * 350_000).encode()  # under 5 MB, far over the row limit
    assert len(data) <= imports.MAX_BYTES
    began = time.perf_counter()
    with pytest.raises(imports.TooLarge):
        imports.parse_file(data, "csv")
    assert time.perf_counter() - began < 1.5  # stops reading at the limit instead of parsing everything


def test_repeated_previews_are_rate_limited_and_create_nothing_public(client: TestClient) -> None:
    who = _author(client)
    with get_sessionmaker()() as db:
        live_before = db.scalar(select(func.count()).select_from(ContentItem).where(ContentItem.availability == "live"))
    chapter, refs = _setup()
    docs = [_doc(_row(f"rl-{n}", chapter, refs, f"Fixture stem {n}")) for n in range(imports.PREVIEWS_PER_HOUR + 1)]
    codes = [_preview(client, who, d).status_code for d in docs]
    assert set(codes[:-1]) == {201} and codes[-1] == 429, codes  # validation is the expensive part
    with get_sessionmaker()() as db:
        live_after = db.scalar(select(func.count()).select_from(ContentItem).where(ContentItem.availability == "live"))
    assert live_after == live_before
