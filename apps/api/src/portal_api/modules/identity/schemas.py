from __future__ import annotations

import uuid
from datetime import datetime
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


class MeOut(BaseModel):
    id: uuid.UUID
    email: str | None
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


class DevTokenIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)
    mfa: bool = False  # development adapter only: asserts a second factor for testing MFA-gated operations


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"  # noqa: S105 (OAuth token type, not a secret)
    expires_in: int
