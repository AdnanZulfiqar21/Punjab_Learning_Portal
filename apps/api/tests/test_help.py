"""P15.S2 help centre: Markdown-subset articles become validated content blocks; drafts are private until a help-centre
staff member with MFA publishes them; versions are immutable; search covers published text; Urdu falls back to
English with a flag; service incidents form a public status with a timeline."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient

from portal_api.db import get_sessionmaker
from portal_api.modules.content import blocks
from portal_api.modules.help import cli, service
from tests.test_content_workflow import Staff


def _staff(client: TestClient, roles: list[str], mfa: bool = False) -> Staff:
    with get_sessionmaker()() as db:
        return Staff(client, db, roles, mfa=mfa)


def test_the_markdown_subset_becomes_valid_blocks() -> None:
    body = service.to_blocks(
        "Intro line one\ncontinues here.\n\n# Heading\n- a\n- b\n1. first\n2. second\n"
        "> Note: be careful\n\n## Sub\nEnd."
    )
    assert body == [
        {"type": "paragraph", "text": "Intro line one continues here."},
        {"type": "heading", "level": 2, "text": "Heading"},
        {"type": "list", "ordered": False, "items": ["a", "b"]},
        {"type": "list", "ordered": True, "items": ["first", "second"]},
        {"type": "callout", "tone": "note", "text": "Note: be careful"},
        {"type": "heading", "level": 3, "text": "Sub"},
        {"type": "paragraph", "text": "End."},
    ]
    parsed, errors = blocks.parse({"blocks": body})
    assert parsed is not None and errors == []


def test_every_bundled_article_parses_into_valid_blocks() -> None:
    files = sorted(cli.DEFAULT_DIR.glob("*/*.md"))
    assert len(files) >= 9
    for f in files:
        a = cli.parse(f)
        assert service.SLUG.match(str(a["slug"])), f
        assert 3 <= len(str(a["title"])) <= 160 and 10 <= len(str(a["summary"])) <= 400, f
        parsed, errors = blocks.parse({"blocks": service.to_blocks(str(a["markdown"]))})
        assert parsed is not None and not errors, (f, errors)


def test_drafts_stay_private_until_an_mfa_staff_member_publishes(client: TestClient) -> None:
    slug = f"fixture-{uuid.uuid4().hex[:8]}"
    support, support_mfa, learner = (
        _staff(client, ["support"]),
        _staff(client, ["support"], mfa=True),
        _staff(client, []),
    )
    draft = {
        "slug": slug,
        "title": "Fixture help article",
        "summary": "A technical fixture used by the help-centre tests.",
        "markdown": "Fixture paragraph about zebrafishword.\n\n# Steps\n- one\n- two",
        "tags": ["fixture"],
    }
    assert client.put("/v1/studio/help/articles", headers=learner.headers, json=draft).status_code == 403
    saved = client.put("/v1/studio/help/articles", headers=support.headers, json=draft)
    assert saved.status_code == 200, saved.text
    art = saved.json()
    assert (art["status"], art["working_version"], art["published"]) == ("draft", 1, False)
    assert client.get(f"/v1/help/articles/{slug}").status_code == 404  # drafts are never public
    # saving identical text makes no new version
    assert client.put("/v1/studio/help/articles", headers=support.headers, json=draft).json()["working_version"] == 1
    no = client.post(f"/v1/studio/help/articles/{art['id']}/publish", headers=support.headers)
    assert no.status_code == 403 and "multi-factor" in no.json()["detail"]
    ok = client.post(f"/v1/studio/help/articles/{art['id']}/publish", headers=support_mfa.headers)
    assert ok.status_code == 200 and ok.json()["published"] is True
    got = client.get(f"/v1/help/articles/{slug}").json()
    assert got["title"] == "Fixture help article" and got["fallback_locale"] is False
    assert got["body"]["blocks"][1] == {"type": "heading", "level": 2, "text": "Steps"}
    found = client.get("/v1/help/articles", params={"q": "zebrafishword"}).json()
    assert [a["slug"] for a in found] == [slug]
    assert client.get(f"/v1/help/articles/{slug}", params={"locale": "ur"}).json()["fallback_locale"] is True
    # a new draft doesn't change what readers see until it is published
    changed = client.put("/v1/studio/help/articles", headers=support.headers, json={**draft, "title": "Fixture v2"})
    assert changed.json()["working_version"] == 2 and changed.json()["unpublished_changes"] is True
    assert client.get(f"/v1/help/articles/{slug}").json()["title"] == "Fixture help article"
    assert client.post(f"/v1/studio/help/articles/{art['id']}/retire", headers=support_mfa.headers).status_code == 200
    assert client.get(f"/v1/help/articles/{slug}").status_code == 404


def test_the_import_command_creates_drafts_once() -> None:
    cli.main([])
    with get_sessionmaker()() as db:
        from sqlalchemy import func, select

        from portal_api.modules.help.models import HelpArticleVersion

        before = db.scalar(select(func.count()).select_from(HelpArticleVersion))
    cli.main([])
    with get_sessionmaker()() as db:
        after = db.scalar(select(func.count()).select_from(HelpArticleVersion))
    assert before == after  # unchanged files create nothing


def test_incidents_form_a_public_status_with_a_timeline(client: TestClient) -> None:
    operator, plain = _staff(client, ["platform_operator"], mfa=True), _staff(client, ["support"], mfa=True)
    body: dict[str, Any] = {
        "title": "Fixture: uploads are slow",
        "message": "Investigating slow uploads.",
        "components": ["uploads"],
    }
    assert client.post("/v1/ops/incidents", headers=plain.headers, json=body).status_code == 403
    opened = client.post("/v1/ops/incidents", headers=operator.headers, json=body)
    assert opened.status_code == 201, opened.text
    iid = opened.json()["id"]
    status = client.get("/v1/status").json()
    assert status["operational"] is False and any(i["id"] == iid for i in status["incidents"])
    fixed = client.post(
        f"/v1/ops/incidents/{iid}/updates",
        headers=operator.headers,
        json={"status": "resolved", "message": "Uploads are back to normal."},
    )
    assert fixed.status_code == 200 and [u["status"] for u in fixed.json()["updates"]] == ["resolved", "investigating"]
    mine = next(i for i in client.get("/v1/status").json()["incidents"] if i["id"] == iid)
    assert mine["resolved_at"] is not None  # still listed for 24 hours after resolution
    again = client.post(
        f"/v1/ops/incidents/{iid}/updates", headers=operator.headers, json={"status": "monitoring", "message": "Again?"}
    )
    assert again.status_code == 409
