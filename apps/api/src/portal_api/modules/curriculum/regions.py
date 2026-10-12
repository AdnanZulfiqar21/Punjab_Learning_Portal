"""Which regions learners can discover (roadmap P05.S4.T2; REGION-01).

The catalogue model has regions, and a class (grade) belongs to one region. Only the released regions
(`released_regions` setting, Punjab by default) are visible to learners: the catalogue, book and chapter pages, lessons,
search, offline packs and every test builder (practice, mock and written) see only their classes. Another region's
technical records can exist (for example while expansion is being prepared) without becoming discoverable. Studio
tools are not filtered, so staff can prepare a region before the owner authorises its release.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from portal_api.config import get_settings
from portal_api.modules.curriculum.models import BookEdition, Grade, Region


def released_grade_ids() -> Select[Any]:
    return (
        select(Grade.id)
        .join(Region, Region.id == Grade.region_id)
        .where(Region.code.in_(get_settings().released_regions))
    )


def released_grade(column: Any = Grade.id) -> ColumnElement[bool]:
    """SQL: this grade id belongs to a released region."""
    clause: ColumnElement[bool] = column.in_(released_grade_ids())
    return clause


def released_region_ids(db: Session) -> list[str]:
    """For raw SQL: the released regions' ids as strings."""
    return [str(i) for i in db.scalars(select(Region.id).where(Region.code.in_(get_settings().released_regions)))]


def book_is_released(db: Session, book: BookEdition) -> bool:
    return db.scalar(select(Grade.id).where(Grade.id == book.grade_id, released_grade())) is not None
