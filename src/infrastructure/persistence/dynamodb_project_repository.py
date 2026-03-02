"""DynamoDB implementation of the ProjectRepository port.

Implements all project persistence operations using DynamoDB as the backing store.
Follows repository-pattern.md: every boto3 call wrapped in try/except ClientError,
_raise_repository_error() logs internally and raises RepositoryError with safe user_message.

Table: ugsys-projects-{env}
  PK: PROJECT#{id}  SK: PROJECT
  GSI-1 (status-index): GSI1PK = STATUS#{status}, GSI1SK = created_at
  GSI-2 (created_by-index): GSI2PK = OWNER#{created_by}, GSI2SK = created_at
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Never

import structlog
from botocore.exceptions import ClientError

from src.domain.entities.form_schema import CustomField, FieldType, FormSchema
from src.domain.entities.project import Project, ProjectImage
from src.domain.exceptions import NotFoundError, RepositoryError
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.value_objects.project_status import ProjectStatus

logger = structlog.get_logger()


class DynamoDBProjectRepository(ProjectRepository):
    """Concrete DynamoDB implementation of ProjectRepository."""

    def __init__(self, table_name: str, client: Any) -> None:  # noqa: ANN401
        self._table_name = table_name
        self._client = client

    # ── Public interface ──────────────────────────────────────────────────────

    async def save(self, project: Project) -> Project:
        """Persist a new project. Raises RepositoryError if project already exists."""
        try:
            await self._client.put_item(
                TableName=self._table_name,
                Item=self._to_item(project),
                ConditionExpression="attribute_not_exists(PK)",
            )
            return project
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise RepositoryError(
                    message=f"Project {project.id} already exists",
                    user_message="An unexpected error occurred",
                    error_code="REPOSITORY_ERROR",
                ) from e
            self._raise_repository_error("save", e)

    async def find_by_id(self, project_id: str) -> Project | None:
        """Find a project by its ULID. Returns None if not found."""
        try:
            response = await self._client.get_item(
                TableName=self._table_name,
                Key={"PK": {"S": f"PROJECT#{project_id}"}, "SK": {"S": "PROJECT"}},
            )
            item = response.get("Item")
            return self._from_item(item) if item else None
        except ClientError as e:
            self._raise_repository_error("find_by_id", e)

    async def update(self, project: Project) -> Project:
        """Update an existing project. Raises NotFoundError if project does not exist."""
        try:
            await self._client.put_item(
                TableName=self._table_name,
                Item=self._to_item(project),
                ConditionExpression="attribute_exists(PK)",
            )
            return project
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise NotFoundError(
                    message=f"Project {project.id} not found for update",
                    user_message="Project not found",
                    error_code="NOT_FOUND",
                ) from e
            self._raise_repository_error("update", e)

    async def delete(self, project_id: str) -> None:
        """Delete a project by its ULID."""
        try:
            await self._client.delete_item(
                TableName=self._table_name,
                Key={"PK": {"S": f"PROJECT#{project_id}"}, "SK": {"S": "PROJECT"}},
            )
        except ClientError as e:
            self._raise_repository_error("delete", e)

    async def list_paginated(
        self,
        page: int,
        page_size: int,
        status_filter: str | None = None,
        category_filter: str | None = None,
    ) -> tuple[list[Project], int]:
        """List projects with pagination. Uses GSI-1 when status filter is set."""
        try:
            if status_filter:
                response = await self._client.query(
                    TableName=self._table_name,
                    IndexName="status-index",
                    KeyConditionExpression="GSI1PK = :status",
                    ExpressionAttributeValues={":status": {"S": f"STATUS#{status_filter}"}},
                )
            else:
                scan_params: dict[str, Any] = {"TableName": self._table_name}
                filter_parts: list[str] = []
                expr_values: dict[str, Any] = {}
                # Filter to only PROJECT items (not subscriptions etc.)
                filter_parts.append("SK = :sk")
                expr_values[":sk"] = {"S": "PROJECT"}
                if category_filter:
                    filter_parts.append("category = :cat")
                    expr_values[":cat"] = {"S": category_filter}
                scan_params["FilterExpression"] = " AND ".join(filter_parts)
                scan_params["ExpressionAttributeValues"] = expr_values
                response = await self._client.scan(**scan_params)

            items = response.get("Items", [])
            projects = [self._from_item(item) for item in items]
            projects.sort(key=lambda p: p.created_at, reverse=True)
            total = len(projects)
            start = (page - 1) * page_size
            page_items = projects[start : start + page_size]
            return page_items, total
        except ClientError as e:
            self._raise_repository_error("list_paginated", e)

    async def list_public(self, limit: int) -> list[Project]:
        """List public projects: status=active AND is_enabled=true, strips notification_emails."""
        try:
            response = await self._client.query(
                TableName=self._table_name,
                IndexName="status-index",
                KeyConditionExpression="#status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": {"S": "active"}},
            )
            items = response.get("Items", [])
            projects = [
                self._from_item(item)
                for item in items
                if item.get("is_enabled", {}).get("BOOL", False)
            ]
            # Strip notification_emails from public results
            for p in projects:
                p.notification_emails = []
            projects.sort(key=lambda p: p.created_at, reverse=True)
            return projects[:limit]
        except ClientError as e:
            self._raise_repository_error("list_public", e)

    async def list_by_query(self, query: Any) -> tuple[list[Project], int]:  # noqa: ANN401
        """List projects matching the query criteria with total count.

        Uses GSI-1 when status filter is set, otherwise scans with filters.
        Applies in-memory sort and pagination.
        """
        try:
            if query.status:
                response = await self._client.query(
                    TableName=self._table_name,
                    IndexName="status-index",
                    KeyConditionExpression="#status = :status",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":status": {"S": query.status},
                    },
                )
            else:
                filter_parts, expr_values = self._build_filter_expression(query)
                scan_params: dict[str, Any] = {"TableName": self._table_name}
                # Always filter to PROJECT items
                filter_parts.append("SK = :sk")
                expr_values[":sk"] = {"S": "PROJECT"}
                if filter_parts:
                    scan_params["FilterExpression"] = " AND ".join(filter_parts)
                    scan_params["ExpressionAttributeValues"] = expr_values
                response = await self._client.scan(**scan_params)

            items = response.get("Items", [])
            projects = [self._from_item(item) for item in items]

            # Apply in-memory sorting
            sort_attr = query.sort_by if hasattr(query, "sort_by") else "created_at"
            reverse = (query.sort_order == "desc") if hasattr(query, "sort_order") else True
            projects.sort(
                key=lambda p: getattr(p, sort_attr, p.created_at),
                reverse=reverse,
            )
            total = len(projects)
            start = (query.page - 1) * query.page_size
            page_items = projects[start : start + query.page_size]
            return page_items, total
        except ClientError as e:
            self._raise_repository_error("list_by_query", e)

    # ── Serialization ─────────────────────────────────────────────────────────

    def _to_item(self, project: Project) -> dict[str, Any]:
        """Convert domain entity to DynamoDB item. Optional fields omitted when empty/None."""
        item: dict[str, Any] = {
            "PK": {"S": f"PROJECT#{project.id}"},
            "SK": {"S": "PROJECT"},
            "id": {"S": project.id},
            "name": {"S": project.name},
            "description": {"S": project.description},
            "status": {"S": project.status.value},
            "is_enabled": {"BOOL": project.is_enabled},
            "max_participants": {"N": str(project.max_participants)},
            "current_participants": {"N": str(project.current_participants)},
            "created_by": {"S": project.created_by},
            "created_at": {"S": project.created_at},
            "updated_at": {"S": project.updated_at},
            # GSI-1 attributes
            "GSI1PK": {"S": f"STATUS#{project.status.value}"},
            "GSI1SK": {"S": project.created_at},
        }
        # Optional fields — only write if non-empty/non-None
        if project.rich_text:
            item["rich_text"] = {"S": project.rich_text}
        if project.category:
            item["category"] = {"S": project.category}
        if project.start_date:
            item["start_date"] = {"S": project.start_date}
        if project.end_date:
            item["end_date"] = {"S": project.end_date}
        if project.notification_emails:
            item["notification_emails"] = {"SS": project.notification_emails}
        if project.enable_subscription_notifications:
            item["enable_subscription_notifications"] = {"BOOL": True}
        if project.images:
            item["images"] = {"S": json.dumps([asdict(img) for img in project.images])}
        if project.form_schema is not None:
            item["form_schema"] = {"S": json.dumps(asdict(project.form_schema))}
        if project.migrated_from:
            item["migrated_from"] = {"S": project.migrated_from}
        if project.migrated_at:
            item["migrated_at"] = {"S": project.migrated_at}
        # GSI-2 for created_by queries
        if project.created_by:
            item["GSI2PK"] = {"S": f"OWNER#{project.created_by}"}
            item["GSI2SK"] = {"S": project.created_at}
        return item

    def _from_item(self, item: dict[str, Any]) -> Project:
        """Convert DynamoDB item to domain entity. Uses .get() with safe defaults."""
        form_schema_raw = item.get("form_schema", {}).get("S")
        form_schema = (
            self._deserialize_form_schema(json.loads(form_schema_raw)) if form_schema_raw else None
        )
        images_raw = item.get("images", {}).get("S")
        images = [ProjectImage(**img) for img in json.loads(images_raw)] if images_raw else []
        return Project(
            id=item["id"]["S"],
            name=item["name"]["S"],
            description=item["description"]["S"],
            rich_text=item.get("rich_text", {}).get("S", ""),
            category=item.get("category", {}).get("S", ""),
            status=ProjectStatus(item["status"]["S"]),
            is_enabled=item.get("is_enabled", {}).get("BOOL", False),
            max_participants=int(item["max_participants"]["N"]),
            current_participants=int(item.get("current_participants", {"N": "0"})["N"]),
            start_date=item.get("start_date", {}).get("S", ""),
            end_date=item.get("end_date", {}).get("S", ""),
            created_by=item["created_by"]["S"],
            notification_emails=list(item.get("notification_emails", {}).get("SS", [])),
            enable_subscription_notifications=item.get("enable_subscription_notifications", {}).get(
                "BOOL", False
            ),
            images=images,
            form_schema=form_schema,
            created_at=item["created_at"]["S"],
            updated_at=item["updated_at"]["S"],
            migrated_from=item.get("migrated_from", {}).get("S"),
            migrated_at=item.get("migrated_at", {}).get("S"),
        )

    @staticmethod
    def _deserialize_form_schema(data: dict[str, Any]) -> FormSchema:
        """Deserialize a JSON dict into a FormSchema domain entity."""
        fields = []
        for f in data.get("fields", []):
            fields.append(
                CustomField(
                    id=f["id"],
                    field_type=FieldType(f["field_type"]),
                    question=f["question"],
                    required=f.get("required", False),
                    options=f.get("options", []),
                )
            )
        return FormSchema(fields=fields)

    def _build_filter_expression(self, query: Any) -> tuple[list[str], dict[str, Any]]:  # noqa: ANN401
        """Build DynamoDB FilterExpression parts from a query object."""
        parts: list[str] = []
        values: dict[str, Any] = {}
        if hasattr(query, "category") and query.category:
            parts.append("category = :cat")
            values[":cat"] = {"S": query.category}
        if hasattr(query, "owner_id") and query.owner_id:
            parts.append("created_by = :owner")
            values[":owner"] = {"S": query.owner_id}
        return parts, values

    # ── Error handling ────────────────────────────────────────────────────────

    def _raise_repository_error(self, operation: str, e: ClientError) -> Never:
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
