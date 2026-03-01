"""
models.py — Pydantic data models for FilePilot AI
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MoveDecision(BaseModel):
    """Schema that the LLM must return as JSON."""

    action: Literal["move"] = "move"
    target_folder: str = Field(
        ...,
        description="Name of the existing folder or a new folder to create.",
        min_length=1,
    )
    reason: str = Field(
        ...,
        description="One-sentence explanation of why the file belongs here.",
        min_length=1,
    )


class FileRecord(BaseModel):
    """Record stored in ChromaDB after a file is moved."""

    id: str = Field(..., description="Unique ID for this record (UUID).")
    filename: str
    extension: str
    original_path: str
    new_path: str
    reason: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
