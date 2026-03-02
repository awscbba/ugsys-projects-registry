"""Abstract repository interface for FormSubmission aggregate root.

Defines the outbound port for form submission persistence operations.
Infrastructure layer provides the concrete DynamoDB implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.form_submission import FormSubmission


class FormSubmissionRepository(ABC):
    """Port interface for form submission persistence operations."""

    @abstractmethod
    async def save(self, submission: FormSubmission) -> FormSubmission: ...

    @abstractmethod
    async def find_by_person_and_project(
        self, person_id: str, project_id: str
    ) -> FormSubmission | None: ...

    @abstractmethod
    async def list_by_project(self, project_id: str) -> list[FormSubmission]: ...
