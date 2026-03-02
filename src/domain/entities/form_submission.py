"""Domain entity for form submissions.

FormSubmission represents a subscriber's responses to a project's dynamic form.

This is a pure dataclass — validation logic belongs in the application layer.
All IDs are ULIDs (string type). All dates are ISO 8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FormSubmission:
    """A subscriber's responses to a project's custom form.

    Attributes:
        id: ULID identifier.
        project_id: ULID of the associated project.
        person_id: ULID of the person who submitted the form.
        responses: Mapping of field_id to response value.
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last update timestamp.
        migrated_from: Source system identifier if migrated (e.g. "registry").
        migrated_at: ISO 8601 timestamp of migration.
    """

    id: str
    project_id: str
    person_id: str
    responses: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    migrated_from: str | None = None
    migrated_at: str | None = None
