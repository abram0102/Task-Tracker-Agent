from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ParsedTask:
    title: str
    raw_input: str
    description: str = ""
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    people: list[str] = field(default_factory=list)
    category: str = "personal"
    priority_score: int = 50
    priority_label: str = "medium"
    priority_reason: str = ""
    suggestion_types: list[str] = field(default_factory=list)


@dataclass
class Task:
    id: int
    title: str
    raw_input: str
    description: str
    start_time: str | None
    end_time: str | None
    location: str | None
    people: list[str]
    category: str
    priority_score: int
    priority_label: str
    priority_reason: str
    status: str
    created_at: datetime
    updated_at: datetime
