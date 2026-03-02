"""Response DTOs for form submission resources.

FormSubmissionResponse: Full form submission data including responses dict.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.domain.entities.form_submission import FormSubmission


@dataclass
class FormSubmissionResponse:
    """Full form submission response including all field responses."""

    id: str
    project_id: str
    person_id: str
    responses: dict[str, Any]
    created_at: str
    updated_at: str
    migrated_from: str | None = None
    migrated_at: str | None = None

    @classmethod
    def from_domain(cls, submission: FormSubmission) -> FormSubmissionResponse:
        """Convert a FormSubmission domain entity to a FormSubmissionResponse DTO."""
        return cls(
            id=submission.id,
            project_id=submission.project_id,
            person_id=submission.person_id,
            responses=dict(submission.responses),
            created_at=submission.created_at,
            updated_at=submission.updated_at,
            migrated_from=submission.migrated_from,
            migrated_at=submission.migrated_at,
        )
