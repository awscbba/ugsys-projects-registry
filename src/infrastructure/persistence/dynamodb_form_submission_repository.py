"""DynamoDB implementation of the FormSubmissionRepository port.

Implements all form submission persistence operations using DynamoDB as the backing store.
Follows repository-pattern.md: every boto3 call wrapped in try/except ClientError,
_raise_repository_error() logs internally and raises RepositoryError with safe user_message.

Table: ugsys-form-submissions-{env}
  PK: SUBMISSION#{id}  SK: SUBMISSION
  GSI-1 (project-index): PK=project_id
  GSI-2 (person-index): PK=person_id
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from botocore.exceptions import ClientError

from src.domain.entities.form_submission import FormSubmission
from src.domain.exceptions import RepositoryError
from src.domain.repositories.form_submission_repository import FormSubmissionRepository

logger = structlog.get_logger()


class DynamoDBFormSubmissionRepository(FormSubmissionRepository):
    """Concrete DynamoDB implementation of FormSubmissionRepository."""

    def __init__(self, table_name: str, client: Any) -> None:  # noqa: ANN401
        self._table_name = table_name
        self._client = client

    # ── Public interface ──────────────────────────────────────────────────────

    async def save(self, submission: FormSubmission) -> FormSubmission:
        """Persist a new form submission. Raises RepositoryError if already exists."""
        try:
            await self._client.put_item(
                TableName=self._table_name,
                Item=self._to_item(submission),
                ConditionExpression="attribute_not_exists(PK)",
            )
            return submission
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise RepositoryError(
                    message=f"FormSubmission {submission.id} already exists",
                    user_message="An unexpected error occurred",
                    error_code="REPOSITORY_ERROR",
                ) from e
            self._raise_repository_error("save", e)

    async def find_by_person_and_project(
        self, person_id: str, project_id: str
    ) -> FormSubmission | None:
        """Find a form submission by person+project using GSI-2 (person-index) with filter.

        Queries person-index by person_id and filters by project_id.
        Returns the first matching submission, or None.
        """
        try:
            response = await self._client.query(
                TableName=self._table_name,
                IndexName="person-index",
                KeyConditionExpression="person_id = :pid",
                FilterExpression="project_id = :proj_id",
                ExpressionAttributeValues={
                    ":pid": {"S": person_id},
                    ":proj_id": {"S": project_id},
                },
            )
            items = response.get("Items", [])
            if items:
                return self._from_item(items[0])
            return None
        except ClientError as e:
            self._raise_repository_error("find_by_person_and_project", e)

    async def list_by_project(self, project_id: str) -> list[FormSubmission]:
        """List all form submissions for a project using GSI-1 (project-index)."""
        try:
            response = await self._client.query(
                TableName=self._table_name,
                IndexName="project-index",
                KeyConditionExpression="project_id = :pid",
                ExpressionAttributeValues={
                    ":pid": {"S": project_id},
                },
            )
            items = response.get("Items", [])
            submissions = [self._from_item(item) for item in items]
            submissions.sort(key=lambda s: s.created_at, reverse=True)
            return submissions
        except ClientError as e:
            self._raise_repository_error("list_by_project", e)

    # ── Serialization ─────────────────────────────────────────────────────────

    def _to_item(self, submission: FormSubmission) -> dict[str, Any]:
        """Convert domain entity to DynamoDB item. Optional fields omitted when empty/None."""
        item: dict[str, Any] = {
            "PK": {"S": f"SUBMISSION#{submission.id}"},
            "SK": {"S": "SUBMISSION"},
            "id": {"S": submission.id},
            "project_id": {"S": submission.project_id},
            "person_id": {"S": submission.person_id},
            "responses": {"S": json.dumps(submission.responses)},
            "created_at": {"S": submission.created_at},
            "updated_at": {"S": submission.updated_at},
        }
        # Optional fields — only write if non-None
        if submission.migrated_from:
            item["migrated_from"] = {"S": submission.migrated_from}
        if submission.migrated_at:
            item["migrated_at"] = {"S": submission.migrated_at}
        return item

    def _from_item(self, item: dict[str, Any]) -> FormSubmission:
        """Convert DynamoDB item to domain entity. Uses .get() with safe defaults."""
        responses_raw = item.get("responses", {}).get("S", "{}")
        return FormSubmission(
            id=item["id"]["S"],
            project_id=item["project_id"]["S"],
            person_id=item["person_id"]["S"],
            responses=json.loads(responses_raw),
            created_at=item.get("created_at", {}).get("S", ""),
            updated_at=item.get("updated_at", {}).get("S", ""),
            migrated_from=item.get("migrated_from", {}).get("S"),
            migrated_at=item.get("migrated_at", {}).get("S"),
        )

    # ── Error handling ────────────────────────────────────────────────────────

    def _raise_repository_error(self, operation: str, e: ClientError) -> None:
        """Log full ClientError internally, raise safe RepositoryError to callers."""
        logger.error(
            "dynamodb.error",
            operation=operation,
            table=self._table_name,
            error_code=e.response["Error"]["Code"],
            error=str(e),
        )
        raise RepositoryError(
            message=f"DynamoDB {operation} failed on {self._table_name}: {e}",
            user_message="An unexpected error occurred",
            error_code="REPOSITORY_ERROR",
        )
