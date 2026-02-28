"""DynamoDB implementation of the SubscriptionRepository port.

Implements all subscription persistence operations using DynamoDB as the backing store.
Follows repository-pattern.md: every boto3 call wrapped in try/except ClientError,
_raise_repository_error() logs internally and raises RepositoryError with safe user_message.

Table: ugsys-subscriptions-{env}
  PK: SUB#{id}  SK: SUB
  GSI-1 (person-index): PK=person_id, SK=created_at
  GSI-2 (project-index): PK=project_id, SK=created_at
  GSI-3 (person-project-index): PK=person_project_key (duplicate detection)
"""

from __future__ import annotations

from typing import Any

import structlog
from botocore.exceptions import ClientError

from src.domain.entities.subscription import Subscription
from src.domain.exceptions import NotFoundError, RepositoryError
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import SubscriptionStatus

logger = structlog.get_logger()


class DynamoDBSubscriptionRepository(SubscriptionRepository):
    """Concrete DynamoDB implementation of SubscriptionRepository."""

    def __init__(self, table_name: str, client: Any) -> None:  # noqa: ANN401
        self._table_name = table_name
        self._client = client

    # ── Public interface ──────────────────────────────────────────────────────

    async def save(self, subscription: Subscription) -> Subscription:
        """Persist a new subscription. Raises RepositoryError if already exists."""
        try:
            await self._client.put_item(
                TableName=self._table_name,
                Item=self._to_item(subscription),
                ConditionExpression="attribute_not_exists(PK)",
            )
            return subscription
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise RepositoryError(
                    message=f"Subscription {subscription.id} already exists",
                    user_message="An unexpected error occurred",
                    error_code="REPOSITORY_ERROR",
                ) from e
            self._raise_repository_error("save", e)

    async def find_by_id(self, subscription_id: str) -> Subscription | None:
        """Find a subscription by its ULID. Returns None if not found."""
        try:
            response = await self._client.get_item(
                TableName=self._table_name,
                Key={"PK": {"S": f"SUB#{subscription_id}"}, "SK": {"S": "SUB"}},
            )
            item = response.get("Item")
            return self._from_item(item) if item else None
        except ClientError as e:
            self._raise_repository_error("find_by_id", e)

    async def update(self, subscription: Subscription) -> Subscription:
        """Update an existing subscription. Raises NotFoundError if not found."""
        try:
            await self._client.put_item(
                TableName=self._table_name,
                Item=self._to_item(subscription),
                ConditionExpression="attribute_exists(PK)",
            )
            return subscription
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise NotFoundError(
                    message=f"Subscription {subscription.id} not found for update",
                    user_message="Subscription not found",
                    error_code="NOT_FOUND",
                ) from e
            self._raise_repository_error("update", e)

    async def find_by_person_and_project(
        self, person_id: str, project_id: str
    ) -> Subscription | None:
        """Find a subscription by person+project using GSI-3 (person-project-index).

        Returns the first non-cancelled subscription found, or None.
        """
        try:
            person_project_key = f"{person_id}#{project_id}"
            response = await self._client.query(
                TableName=self._table_name,
                IndexName="person-project-index",
                KeyConditionExpression="person_project_key = :ppk",
                ExpressionAttributeValues={
                    ":ppk": {"S": person_project_key},
                },
            )
            items = response.get("Items", [])
            # Return the first non-cancelled subscription
            for item in items:
                sub = self._from_item(item)
                if sub.status != SubscriptionStatus.CANCELLED:
                    return sub
            return None
        except ClientError as e:
            self._raise_repository_error("find_by_person_and_project", e)

    async def list_by_project(
        self, project_id: str, page: int, page_size: int
    ) -> tuple[list[Subscription], int]:
        """List subscriptions for a project using GSI-2 (project-index), paginated."""
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
            subscriptions = [self._from_item(item) for item in items]
            subscriptions.sort(key=lambda s: s.created_at, reverse=True)
            total = len(subscriptions)
            start = (page - 1) * page_size
            page_items = subscriptions[start : start + page_size]
            return page_items, total
        except ClientError as e:
            self._raise_repository_error("list_by_project", e)

    async def list_by_person(self, person_id: str) -> list[Subscription]:
        """List all subscriptions for a person using GSI-1 (person-index)."""
        try:
            response = await self._client.query(
                TableName=self._table_name,
                IndexName="person-index",
                KeyConditionExpression="person_id = :pid",
                ExpressionAttributeValues={
                    ":pid": {"S": person_id},
                },
            )
            items = response.get("Items", [])
            subscriptions = [self._from_item(item) for item in items]
            subscriptions.sort(key=lambda s: s.created_at, reverse=True)
            return subscriptions
        except ClientError as e:
            self._raise_repository_error("list_by_person", e)

    async def cancel_all_for_person(self, person_id: str) -> int:
        """Cancel all active/pending subscriptions for a person.

        Returns the count of cancelled subscriptions.
        """
        try:
            # Fetch all subscriptions for this person via GSI-1
            response = await self._client.query(
                TableName=self._table_name,
                IndexName="person-index",
                KeyConditionExpression="person_id = :pid",
                ExpressionAttributeValues={
                    ":pid": {"S": person_id},
                },
            )
            items = response.get("Items", [])
            cancelled_count = 0
            for item in items:
                sub = self._from_item(item)
                if sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING):
                    sub.status = SubscriptionStatus.CANCELLED
                    sub.is_active = False
                    await self._client.put_item(
                        TableName=self._table_name,
                        Item=self._to_item(sub),
                    )
                    cancelled_count += 1
            return cancelled_count
        except ClientError as e:
            self._raise_repository_error("cancel_all_for_person", e)

    # ── Serialization ─────────────────────────────────────────────────────────

    def _to_item(self, subscription: Subscription) -> dict[str, Any]:
        """Convert domain entity to DynamoDB item. Optional fields omitted when empty/None."""
        item: dict[str, Any] = {
            "PK": {"S": f"SUB#{subscription.id}"},
            "SK": {"S": "SUB"},
            "id": {"S": subscription.id},
            "project_id": {"S": subscription.project_id},
            "person_id": {"S": subscription.person_id},
            "status": {"S": subscription.status.value},
            "is_active": {"BOOL": subscription.is_active},
            "created_at": {"S": subscription.created_at},
            "updated_at": {"S": subscription.updated_at},
            # GSI-3 composite key for duplicate detection
            "person_project_key": {"S": f"{subscription.person_id}#{subscription.project_id}"},
        }
        # Optional fields — only write if non-empty/non-None
        if subscription.notes:
            item["notes"] = {"S": subscription.notes}
        if subscription.subscription_date:
            item["subscription_date"] = {"S": subscription.subscription_date}
        if subscription.migrated_from:
            item["migrated_from"] = {"S": subscription.migrated_from}
        if subscription.migrated_at:
            item["migrated_at"] = {"S": subscription.migrated_at}
        return item

    def _from_item(self, item: dict[str, Any]) -> Subscription:
        """Convert DynamoDB item to domain entity. Uses .get() with safe defaults."""
        return Subscription(
            id=item["id"]["S"],
            project_id=item["project_id"]["S"],
            person_id=item["person_id"]["S"],
            status=SubscriptionStatus(item["status"]["S"]),
            notes=item.get("notes", {}).get("S", ""),
            subscription_date=item.get("subscription_date", {}).get("S", ""),
            is_active=item.get("is_active", {}).get("BOOL", True),
            created_at=item["created_at"]["S"],
            updated_at=item["updated_at"]["S"],
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
