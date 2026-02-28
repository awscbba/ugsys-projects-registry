"""Application service for dynamic form schema management and form submissions.

FormService orchestrates:
- Updating a project's form schema (with validation)
- Submitting form responses
- Retrieving and listing form submissions

Architecture: application layer — imports only from src.domain.* and src.application.*
"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from ulid import ULID

from src.application.commands.form_commands import SubmitFormCommand, UpdateFormSchemaCommand
from src.application.dtos.form_dtos import FormSubmissionResponse
from src.application.dtos.project_dtos import ProjectResponse
from src.application.tracing import traced
from src.domain.entities.form_schema import FieldType, FormSchema
from src.domain.entities.form_submission import FormSubmission
from src.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from src.domain.repositories.form_submission_repository import FormSubmissionRepository
from src.domain.repositories.project_repository import ProjectRepository

logger = structlog.get_logger()


class FormService:
    """Application service for form schema and submission operations."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        form_submission_repo: FormSubmissionRepository,
    ) -> None:
        self._project_repo = project_repo
        self._form_submission_repo = form_submission_repo

    @traced
    async def update_schema(self, cmd: UpdateFormSchemaCommand) -> ProjectResponse:
        """Update the dynamic form schema for a project.

        Validates field count, uniqueness, poll options, and serialized size
        before persisting the schema on the project.
        """
        logger.info("form_service.update_schema.started", project_id=cmd.project_id)
        start = time.perf_counter()

        project = await self._project_repo.find_by_id(cmd.project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project {cmd.project_id} not found",
                user_message="Project not found",
                error_code="PROJECT_NOT_FOUND",
            )

        if not cmd.is_admin and project.created_by != cmd.requester_id:
            raise AuthorizationError(
                message=(
                    f"User {cmd.requester_id} attempted to update form schema "
                    f"for project {cmd.project_id} owned by {project.created_by}"
                ),
                user_message="Access denied",
                error_code="FORBIDDEN",
            )

        if len(cmd.fields) > 20:
            raise ValidationError(
                message=f"Form schema has {len(cmd.fields)} fields, max is 20",
                user_message="Form schema cannot have more than 20 fields",
                error_code="FORM_SCHEMA_TOO_MANY_FIELDS",
            )

        field_ids = [f.id for f in cmd.fields]
        if len(field_ids) != len(set(field_ids)):
            raise ValidationError(
                message=f"Form schema has duplicate field IDs: {field_ids}",
                user_message="Form schema has duplicate field IDs",
                error_code="FORM_SCHEMA_DUPLICATE_FIELD_IDS",
            )

        for f in cmd.fields:
            if f.field_type in (FieldType.POLL_SINGLE, FieldType.POLL_MULTIPLE) and (
                len(f.options) < 2 or len(f.options) > 10
            ):
                raise ValidationError(
                    message=(
                        f"Poll field '{f.id}' has {len(f.options)} options, "
                        "must be between 2 and 10"
                    ),
                    user_message="Poll fields must have between 2 and 10 options",
                    error_code="FORM_SCHEMA_INVALID_OPTIONS",
                )

        fields_data: list[dict[str, Any]] = [
            {
                "id": f.id,
                "field_type": f.field_type,
                "question": f.question,
                "required": f.required,
                "options": f.options,
            }
            for f in cmd.fields
        ]
        json_str = json.dumps(fields_data)
        if len(json_str) > 50 * 1024:
            raise ValidationError(
                message=f"Form schema serialized size {len(json_str)} bytes exceeds 50KB limit",
                user_message="Form schema is too large",
                error_code="FORM_SCHEMA_TOO_LARGE",
            )

        project.form_schema = FormSchema(fields=cmd.fields)
        project.updated_at = datetime.now(UTC).isoformat()

        updated = await self._project_repo.update(project)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "form_service.update_schema.completed",
            project_id=cmd.project_id,
            field_count=len(cmd.fields),
            duration_ms=duration_ms,
        )
        return ProjectResponse.from_domain(updated)

    @traced
    async def submit(self, cmd: SubmitFormCommand) -> FormSubmissionResponse:
        """Submit form responses for a project.

        Validates required fields and poll response values before persisting.
        """
        logger.info(
            "form_service.submit.started",
            project_id=cmd.project_id,
            person_id=cmd.person_id,
        )
        start = time.perf_counter()

        project = await self._project_repo.find_by_id(cmd.project_id)
        if project is None:
            raise NotFoundError(
                message=f"Project {cmd.project_id} not found",
                user_message="Project not found",
                error_code="PROJECT_NOT_FOUND",
            )

        if project.form_schema is None:
            raise ValidationError(
                message=f"Project {cmd.project_id} has no form schema",
                user_message="This project does not have a form",
                error_code="PROJECT_HAS_NO_FORM_SCHEMA",
            )

        for f in project.form_schema.fields:
            if f.required:
                value = cmd.responses.get(f.id)
                if value is None or value == "" or value == [] or value == {}:
                    raise ValidationError(
                        message=(
                            f"Required field '{f.id}' ('{f.question}') "
                            f"missing in submission for project {cmd.project_id}"
                        ),
                        user_message=f"Required field '{f.question}' is missing",
                        error_code="FORM_SUBMISSION_MISSING_REQUIRED_FIELD",
                    )

        for f in project.form_schema.fields:
            if f.field_type == FieldType.POLL_SINGLE and f.id in cmd.responses:
                response_value = cmd.responses[f.id]
                if response_value not in f.options:
                    raise ValidationError(
                        message=(
                            f"Invalid response '{response_value}' for poll_single "
                            f"field '{f.id}' in project {cmd.project_id}"
                        ),
                        user_message=f"Invalid response for field '{f.question}'",
                        error_code="FORM_SUBMISSION_INVALID_RESPONSE",
                    )

            if f.field_type == FieldType.POLL_MULTIPLE and f.id in cmd.responses:
                response_value = cmd.responses[f.id]
                if not isinstance(response_value, list) or not all(
                    v in f.options for v in response_value
                ):
                    raise ValidationError(
                        message=(
                            f"Invalid response '{response_value}' for poll_multiple "
                            f"field '{f.id}' in project {cmd.project_id}"
                        ),
                        user_message=f"Invalid response for field '{f.question}'",
                        error_code="FORM_SUBMISSION_INVALID_RESPONSE",
                    )

        now = datetime.now(UTC).isoformat()
        submission_id = str(ULID())
        submission = FormSubmission(
            id=submission_id,
            project_id=cmd.project_id,
            person_id=cmd.person_id,
            responses=cmd.responses,
            created_at=now,
            updated_at=now,
        )

        saved = await self._form_submission_repo.save(submission)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "form_service.submit.completed",
            project_id=cmd.project_id,
            person_id=cmd.person_id,
            submission_id=submission_id,
            duration_ms=duration_ms,
        )
        return FormSubmissionResponse.from_domain(saved)

    @traced
    async def get_submission(
        self,
        submission_id: str,
        person_id: str,
        project_id: str,
        is_admin: bool,
    ) -> FormSubmissionResponse:
        """Retrieve a form submission with IDOR protection."""
        logger.info(
            "form_service.get_submission.started",
            submission_id=submission_id,
            project_id=project_id,
        )
        start = time.perf_counter()

        submission = await self._form_submission_repo.find_by_person_and_project(
            person_id, project_id
        )
        if submission is None:
            raise NotFoundError(
                message=(
                    f"Form submission not found for person {person_id} and project {project_id}"
                ),
                user_message="Form submission not found",
                error_code="FORM_SUBMISSION_NOT_FOUND",
            )

        if not is_admin and submission.person_id != person_id:
            raise AuthorizationError(
                message=(
                    f"User {person_id} attempted IDOR on submission "
                    f"belonging to {submission.person_id}"
                ),
                user_message="Access denied",
                error_code="FORBIDDEN",
            )

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "form_service.get_submission.completed",
            submission_id=submission_id,
            duration_ms=duration_ms,
        )
        return FormSubmissionResponse.from_domain(submission)

    @traced
    async def list_by_project(self, project_id: str) -> list[FormSubmissionResponse]:
        """List all form submissions for a project (admin only)."""
        logger.info("form_service.list_by_project.started", project_id=project_id)
        start = time.perf_counter()

        submissions = await self._form_submission_repo.list_by_project(project_id)

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "form_service.list_by_project.completed",
            project_id=project_id,
            count=len(submissions),
            duration_ms=duration_ms,
        )
        return [FormSubmissionResponse.from_domain(s) for s in submissions]
