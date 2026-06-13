from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class UserShariahOverride(BaseModel):
    ticker: str
    direction: Literal["include", "exclude"]
    added_at: str | None = None
    note: str | None = None


class ShariahStatus(BaseModel):
    ticker: str
    is_compliant: bool
    source_kind: Literal["external", "user", "excluded_by_user", "not_listed"]
    external_source_name: str | None = None
    external_source_as_of: str | None = None
    is_stale: bool = False
    source_url: str | None = None
    user_note: str | None = None
    conflict: bool = False
    active_sources: list[str] = Field(default_factory=list)


class ShariahStatusResponse(ShariahStatus):
    data_as_of: str
    disclaimer: str
