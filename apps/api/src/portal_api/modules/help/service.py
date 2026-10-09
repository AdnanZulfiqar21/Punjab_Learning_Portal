"""Help articles and incident notices (P15.S2.T1/T3).

Articles are written in a small Markdown subset (``#``/``##`` headings, ``-`` or ``1.`` lists, ``> Note:`` callouts and
paragraphs), converted to the same validated content blocks lessons use, so web and native render them with the
existing renderers. Every save makes a new immutable version; staff with ``manage_help`` draft, and publishing also
needs an MFA session. Readers only ever see published versions; a missing Urdu version falls back to English and says
so. Search uses PostgreSQL full-text search over published text only.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from portal_api.errors import Conflict, Forbidden, NotFound, Unprocessable
from portal_api.modules.audit.models import record
from portal_api.modules.content import blocks
from portal_api.modules.help.models import HelpArticle, HelpArticleVersion, ServiceIncident, ServiceIncidentUpdate
from portal_api.modules.identity.deps import Principal

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
INCIDENT_STATUSES = ("investigating", "identified", "monitoring", "resolved")


# ------------------------------------------------------------------ Markdown subset -> blocks
def to_blocks(markdown: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    para: list[str] = []
    items: list[str] = []
    ordered = False

    def flush() -> None:
        nonlocal para, items
        if para:
            out.append({"type": "paragraph", "text": " ".join(para)})
            para = []
        if items:
            out.append({"type": "list", "ordered": ordered, "items": items})
            items = []

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("## "):
            flush()
            out.append({"type": "heading", "level": 3, "text": line[3:].strip()})
        elif line.startswith("# "):
            flush()
            out.append({"type": "heading", "level": 2, "text": line[2:].strip()})
        elif line.startswith("> "):
            flush()
            out.append({"type": "callout", "tone": "note", "text": line[2:].strip()})
        elif re.match(r"^(-|\d+\.)\s+", line):
            if para:
                out.append({"type": "paragraph", "text": " ".join(para)})
                para = []
            is_ordered = not line.startswith("-")
            if items and is_ordered != ordered:
                flush()
            ordered = is_ordered
            items.append(re.sub(r"^(-|\d+\.)\s+", "", line))
        else:
            if items:
                flush()
            para.append(line)
    flush()
    return out


def _plain(body: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for b in body:
        parts += [b["text"]] if "text" in b else list(b.get("items", []))
    return " ".join(parts)


# ------------------------------------------------------------------ authoring
def _manage(who: Principal, *, publish: bool = False) -> None:
    from portal_api.modules.identity.permissions import Permission

    if Permission.manage_help not in who.permissions:
        raise Forbidden("Only help-centre staff can change help articles.")
    if publish and not who.claims.mfa:
        raise Forbidden("This action needs a multi-factor authenticated session. Sign in again with MFA.")


def save_draft(
    db: Session,
    who: Principal | None,
    *,
    slug: str,
    locale: str,
    title: str,
    summary: str,
    markdown: str,
    tags: list[str],
) -> HelpArticle:
    """Create or update an article's working version. ``who`` is None only for the trusted import command."""
    if who is not None:
        _manage(who)
    if not SLUG.match(slug) or len(slug) > 80:
        raise Unprocessable("Use a short lowercase slug with hyphens, for example 'upload-limits'.")
    if locale not in ("en", "ur"):
        raise Unprocessable("Help articles are in English (en) or Urdu (ur).")
    if not (3 <= len(title.strip()) <= 160) or not (10 <= len(summary.strip()) <= 400):
        raise Unprocessable("Give a title (3-160 characters) and a one-line summary (10-400 characters).")
    body = to_blocks(markdown)
    parsed, errors = blocks.parse({"blocks": body})
    if parsed is None or not body:
        raise Unprocessable("The article text isn't valid.", errors=errors or ["The article is empty."])
    source_hash = hashlib.sha256(f"{title}\n{summary}\n{markdown}\n{sorted(tags)}".encode()).hexdigest()
    article = db.scalar(
        select(HelpArticle).where(HelpArticle.slug == slug, HelpArticle.locale == locale).with_for_update()
    )
    if article is None:
        article = HelpArticle(id=uuid.uuid4(), slug=slug, locale=locale)
        db.add(article)
        db.flush()
    current = db.get(HelpArticleVersion, article.working_version_id) if article.working_version_id else None
    if current is not None and current.source_hash == source_hash:
        db.commit()
        return article  # unchanged: re-importing creates nothing
    number = (
        db.scalar(select(func.max(HelpArticleVersion.number)).where(HelpArticleVersion.article_id == article.id)) or 0
    ) + 1
    v = HelpArticleVersion(
        id=uuid.uuid4(),
        article_id=article.id,
        number=number,
        title=title.strip(),
        summary=summary.strip(),
        body={"blocks": body},
        tags=sorted({t.strip().lower() for t in tags if t.strip()}),
        search_text=f"{title} {summary} {_plain(body)} {' '.join(tags)}",
        source_hash=source_hash,
        created_by=who.user.id if who else None,
    )
    db.add(v)
    db.flush()
    article.working_version_id = v.id
    article.updated_at = func.now()
    record(
        db,
        actor=who.user.id if who else None,
        action="help.drafted",
        target_type="help_article",
        target_id=str(article.id),
        details={"slug": slug, "locale": locale, "version": number},
    )
    db.commit()
    return article


def publish(db: Session, who: Principal, article_id: uuid.UUID) -> HelpArticle:
    _manage(who, publish=True)
    article = db.scalar(select(HelpArticle).where(HelpArticle.id == article_id).with_for_update())
    if article is None:
        raise NotFound("Article not found.")
    if article.working_version_id is None or article.working_version_id == article.published_version_id:
        raise Conflict("There is no new version to publish.", code_reason="NOTHING_TO_PUBLISH")
    v = db.get(HelpArticleVersion, article.working_version_id)
    assert v is not None
    v.published_at = func.now()
    v.published_by = who.user.id
    article.published_version_id = v.id
    article.status = "published"
    article.updated_at = func.now()
    record(
        db,
        actor=who.user.id,
        action="help.published",
        target_type="help_article",
        target_id=str(article.id),
        details={"slug": article.slug, "locale": article.locale, "version": v.number},
    )
    db.commit()
    return article


def retire(db: Session, who: Principal, article_id: uuid.UUID) -> HelpArticle:
    _manage(who, publish=True)
    article = db.get(HelpArticle, article_id)
    if article is None:
        raise NotFound("Article not found.")
    article.status = "retired"
    article.updated_at = func.now()
    record(
        db, actor=who.user.id, action="help.retired", target_type="help_article", target_id=str(article.id), details={}
    )
    db.commit()
    return article


def staff_list(db: Session, who: Principal) -> list[tuple[HelpArticle, HelpArticleVersion | None]]:
    _manage(who)
    rows = list(db.scalars(select(HelpArticle).order_by(HelpArticle.slug, HelpArticle.locale)))
    return [(a, db.get(HelpArticleVersion, a.working_version_id) if a.working_version_id else None) for a in rows]


# ------------------------------------------------------------------ reading
def search(db: Session, q: str, locale: str, limit: int) -> list[tuple[HelpArticle, HelpArticleVersion]]:
    """Published articles in a language, best match first (or alphabetical when there is no query)."""
    stmt = (
        select(HelpArticle, HelpArticleVersion)
        .join(HelpArticleVersion, HelpArticleVersion.id == HelpArticle.published_version_id)
        .where(HelpArticle.status == "published", HelpArticle.locale == locale)
    )
    q = q.strip()
    if q:
        doc = func.to_tsvector(text("'simple'"), HelpArticleVersion.search_text)
        query = func.websearch_to_tsquery(text("'simple'"), q)
        stmt = stmt.where(doc.op("@@")(query)).order_by(func.ts_rank(doc, query).desc(), HelpArticleVersion.title)
    else:
        stmt = stmt.order_by(HelpArticleVersion.title)
    return [(a, v) for a, v in db.execute(stmt.limit(limit)).tuples()]


def read(db: Session, slug: str, locale: str) -> tuple[HelpArticle, HelpArticleVersion, bool]:
    """The published article, falling back to English when the requested language has none (flagged)."""
    for loc, fallback in ((locale, False), ("en", locale != "en")):
        a = db.scalar(
            select(HelpArticle).where(
                HelpArticle.slug == slug, HelpArticle.locale == loc, HelpArticle.status == "published"
            )
        )
        if a is not None and a.published_version_id is not None:
            v = db.get(HelpArticleVersion, a.published_version_id)
            assert v is not None
            return a, v, fallback
    raise NotFound("Help article not found.")


# ------------------------------------------------------------------ incidents
def open_incident(db: Session, who: Principal, title: str, message: str, components: list[str]) -> ServiceIncident:
    i = ServiceIncident(id=uuid.uuid4(), title=title.strip(), components=components, created_by=who.user.id)
    db.add(i)
    db.flush()
    db.add(ServiceIncidentUpdate(incident_id=i.id, status="investigating", message=message.strip(), by=who.user.id))
    record(
        db,
        actor=who.user.id,
        action="incident.opened",
        target_type="service_incident",
        target_id=str(i.id),
        details={"title": title},
    )
    db.commit()
    return i


def update_incident(db: Session, who: Principal, incident_id: uuid.UUID, status: str, message: str) -> ServiceIncident:
    if status not in INCIDENT_STATUSES:
        raise Unprocessable("Unknown incident status.")
    i = db.scalar(select(ServiceIncident).where(ServiceIncident.id == incident_id).with_for_update())
    if i is None:
        raise NotFound("Incident not found.")
    if i.status == "resolved":
        raise Conflict("This incident is resolved; open a new one if the problem returns.")
    i.status = status
    i.updated_at = func.now()
    if status == "resolved":
        i.resolved_at = func.now()
    db.add(ServiceIncidentUpdate(incident_id=i.id, status=status, message=message.strip(), by=who.user.id))
    record(
        db,
        actor=who.user.id,
        action="incident.updated",
        target_type="service_incident",
        target_id=str(i.id),
        details={"status": status},
    )
    db.commit()
    return i


def current_incidents(db: Session) -> list[tuple[ServiceIncident, list[ServiceIncidentUpdate]]]:
    """Unresolved incidents plus those resolved in the last 24 hours, newest first, each with its timeline."""
    rows = db.scalars(
        select(ServiceIncident)
        .where(
            (ServiceIncident.resolved_at.is_(None))
            | (ServiceIncident.resolved_at > func.now() - text("interval '24 hours'"))
        )
        .order_by(ServiceIncident.started_at.desc())
        .limit(20)
    ).all()
    return [
        (
            i,
            list(
                db.scalars(
                    select(ServiceIncidentUpdate)
                    .where(ServiceIncidentUpdate.incident_id == i.id)
                    .order_by(ServiceIncidentUpdate.at.desc())
                )
            ),
        )
        for i in rows
    ]
