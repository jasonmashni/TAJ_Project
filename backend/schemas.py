"""Pydantic models for the HTTP/JSON surface (SRS review + config)."""

from __future__ import annotations

from pydantic import BaseModel


class ReviewRequest(BaseModel):
    item_id: int
    quality: int  # 0-5 (SM-2 grade)


class ConfigResponse(BaseModel):
    language: str
    name: str
    native_name: str
    dialect: str
    rtl: bool
    level: str
    providers: dict[str, str]
