from __future__ import annotations

import re
import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from portal_api.modules.identity.permissions import Role

Stream = Literal["pre_medical", "pre_engineering", "ics"]
SubjectCode = Literal["biology", "chemistry", "physics", "computer_science", "mathematics"]
ExamCode = Literal["mdcat", "ecat"]
Language = Literal["en", "ur", "roman_ur"]
ConsentDocument = Literal["terms", "privacy", "marketing_messages"]


class ProfileIn(BaseModel):
    """Onboarding answers (P04.S3.T1). Everything can be corrected later; no identity documents are collected."""

    model_config = ConfigDict(extra="forbid")
    grade: Literal[11, 12] | None = None
    stream: Stream | None = None
    subjects: list[SubjectCode] = Field(default_factory=list, max_length=5)
    target_exams: list[ExamCode] = Field(default_factory=list, max_length=2)
    target_year: int | None = Field(default=None, ge=2026, le=2035)
    explanation_language: Language = "en"
    daily_minutes: int | None = Field(default=None, ge=10, le=600)

    @field_validator("subjects", "target_exams")
    @classmethod
    def _unique(cls, v: list[str]) -> list[str]:
        if len(set(v)) != len(v):
            raise ValueError("duplicate values")
        return v


class ProfileOut(ProfileIn):
    model_config = ConfigDict(from_attributes=True, extra="ignore")
    updated_at: datetime | None = None


class ConsentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document: ConsentDocument
    version: str = Field(min_length=1, max_length=40)


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    document: str
    version: str
    accepted_at: datetime
    withdrawn_at: datetime | None


class RoleGrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    role: str
    scope: dict[str, Any]
    granted_by: uuid.UUID | None
    granted_at: datetime
    reason: str
    revoked_at: datetime | None
    revoke_reason: str | None


NAME_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|[ .'\-])*")


def normalize_phone(value: str) -> str:
    """AUTH-PASSWORD-01: a mobile number in E.164. Pakistani numbers may be typed locally (0300 1234567, 92300…);
    others need their + country code. Spaces, dashes, dots and brackets are ignored. Not verified."""
    raw = re.sub(r"[\s\-().]", "", value or "")
    if re.fullmatch(r"03\d{9}", raw):
        raw = "+92" + raw[1:]
    elif re.fullmatch(r"923\d{9}", raw):
        raw = "+" + raw
    elif raw.startswith("00"):
        raw = "+" + raw[2:]
    if raw.startswith("+92") and not re.fullmatch(r"\+923\d{9}", raw):
        raise ValueError("Enter a Pakistani mobile number like 0300 1234567.")
    if not re.fullmatch(r"\+[1-9]\d{7,14}", raw):
        raise ValueError("Enter a mobile number like 0300 1234567 (or +country code for other countries).")
    return raw


def clean_name(value: str) -> str:
    """AUTH-PASSWORD-01: a first name or surname as typed, with spaces tidied. Letters in any script, spaces, dots,
    apostrophes and hyphens; no digits or symbols."""
    name = " ".join((value or "").split())
    if not name or not NAME_RE.fullmatch(name):
        raise ValueError("Enter your name in letters.")
    return name


def check_date_of_birth(value: date, today: date | None = None) -> date:
    """AUTH-PASSWORD-01: a plausible date of birth for a learner (between 8 and 100 years old). Not verified."""
    today = today or date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
    if value > today or age < 8 or age > 100:
        raise ValueError("Enter your real date of birth.")
    return value


class MeOut(BaseModel):
    id: uuid.UUID
    email: str | None
    first_name: str | None = None
    surname: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    display_name: str | None
    status: str
    roles: list[Role]
    mfa_session: bool
    profile: ProfileOut | None
    consents: list[ConsentOut]


class RoleGrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Role
    scope: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=5, max_length=500)


class RevokeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=5, max_length=500)


class DevRegisterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    display_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)  # optional for the development shortcut

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None


class DevTokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    mfa: bool = False  # development adapter only: asserts a second factor for testing MFA-gated operations


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 (OAuth token type, not a secret)
    expires_in: int


class SessionCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["web", "native"]
    device_label: str | None = Field(default=None, max_length=120)


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    kind: str
    device_label: str | None
    user_agent: str | None
    mfa: bool
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    current: bool = False


class SessionCreatedOut(BaseModel):
    session_token: str
    session: SessionOut
