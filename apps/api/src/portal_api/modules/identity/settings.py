"""Personal study settings (roadmap P04.S3.T2; SETTINGS-01).

The account keeps the learner's *usual* settings: theme, text size, reduced motion and data saver (how a device shows
the portal), and video quality (for the lecture player, B05). Study reminders stay with the notification preferences
(`/v1/me/notification-preferences`), not here.

Each device keeps its own copy of the display and accessibility settings, and that copy wins on that device: a
device that has its own settings never has them overwritten by a change made elsewhere. A device without its own
(a new device, or one set to "use my usual settings") follows the account's. The operating system's own accessibility
settings are never overridden: reduced motion is on if either the system or the learner asks for it, and the system
theme is used while the theme is "system". Clients enforce this; the API only stores the usual settings.

Changes are partial (PATCH): two devices changing different settings never undo each other.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from portal_api.db import Base, get_session
from portal_api.modules.identity.deps import CurrentPrincipal

router = APIRouter(prefix="/v1", tags=["settings"])
DB = Annotated[Session, Depends(get_session)]

Theme = Literal["system", "light", "dark"]
TextSize = Literal["default", "large", "larger"]
VideoQuality = Literal["auto", "data_saver", "standard", "high"]


class StudySettings(Base):
    __tablename__ = "study_settings"
    __table_args__ = (
        CheckConstraint("theme in ('system','light','dark')", name="study_settings_theme"),
        CheckConstraint("text_size in ('default','large','larger')", name="study_settings_text_size"),
        CheckConstraint(
            "video_quality in ('auto','data_saver','standard','high')", name="study_settings_video_quality"
        ),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    theme: Mapped[str] = mapped_column(String(8), default="system")
    text_size: Mapped[str] = mapped_column(String(8), default="default")
    reduce_motion: Mapped[bool] = mapped_column(Boolean, default=False)
    data_saver: Mapped[bool] = mapped_column(Boolean, default=False)
    video_quality: Mapped[str] = mapped_column(String(12), default="auto")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StudySettingsOut(BaseModel):
    theme: Theme
    text_size: TextSize
    reduce_motion: bool
    data_saver: bool
    video_quality: VideoQuality
    saved: bool  # false: nothing saved yet, these are the defaults
    updated_at: datetime | None


class StudySettingsPatch(BaseModel):
    """Only the settings given are changed."""

    model_config = ConfigDict(extra="forbid")
    theme: Theme | None = None
    text_size: TextSize | None = None
    reduce_motion: bool | None = None
    data_saver: bool | None = None
    video_quality: VideoQuality | None = None

    @model_validator(mode="after")
    def _something(self) -> StudySettingsPatch:
        if not self.model_dump(exclude_none=True):
            raise ValueError("give at least one setting to change")
        return self


DEFAULTS = StudySettingsOut(
    theme="system",
    text_size="default",
    reduce_motion=False,
    data_saver=False,
    video_quality="auto",
    saved=False,
    updated_at=None,
)


def _out(row: StudySettings | None) -> StudySettingsOut:
    if row is None:
        return DEFAULTS
    return StudySettingsOut(
        theme=row.theme,  # type: ignore[arg-type]
        text_size=row.text_size,  # type: ignore[arg-type]
        reduce_motion=row.reduce_motion,
        data_saver=row.data_saver,
        video_quality=row.video_quality,  # type: ignore[arg-type]
        saved=True,
        updated_at=row.updated_at,
    )


@router.get("/me/settings", response_model=StudySettingsOut, summary="Your usual study settings (defaults if unsaved)")
def get_settings(db: DB, who: CurrentPrincipal) -> StudySettingsOut:
    return _out(db.get(StudySettings, who.user.id))


@router.patch(
    "/me/settings",
    response_model=StudySettingsOut,
    summary="Change some of your usual study settings; the others are left as they are",
)
def change_settings(db: DB, who: CurrentPrincipal, body: StudySettingsPatch) -> StudySettingsOut:
    changes = body.model_dump(exclude_none=True)
    db.execute(
        insert(StudySettings)
        .values(user_id=who.user.id, **{**_defaults(), **changes})
        .on_conflict_do_update(index_elements=["user_id"], set_={**changes, "updated_at": func.now()})
    )
    db.commit()
    return _out(db.get(StudySettings, who.user.id, populate_existing=True))


def _defaults() -> dict[str, object]:
    return DEFAULTS.model_dump(exclude={"saved", "updated_at"})
