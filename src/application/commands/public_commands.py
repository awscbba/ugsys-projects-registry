"""Command dataclasses for public (unauthenticated) write operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PublicRegisterCommand:
    """Command to register a new user via the public endpoint."""

    email: str
    first_name: str
    last_name: str
    password: str


@dataclass
class PublicSubscribeCommand:
    """Command to subscribe to a project via the public endpoint."""

    project_id: str
    email: str
    first_name: str
    last_name: str
    notes: str | None = None
    form_responses: dict[str, Any] = field(default_factory=dict)
