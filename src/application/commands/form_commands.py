"""Command dataclasses for form schema and submission write operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.domain.entities.form_schema import CustomField


@dataclass
class UpdateFormSchemaCommand:
    """Command to update the dynamic form schema for a project."""

    project_id: str
    requester_id: str
    is_admin: bool
    fields: list[CustomField]


@dataclass
class SubmitFormCommand:
    """Command to submit a form response for a project."""

    project_id: str
    person_id: str
    responses: dict[str, Any] = field(default_factory=dict)
