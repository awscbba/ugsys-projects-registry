"""Integration tests for DynamoDBSubscriptionRepository using moto mock_aws.

Tests cover:
- save/find_by_id round-trip for all fields including optional ones
- Duplicate save raises RepositoryError
- find_by_person_and_project via GSI-3 returns correct subscription
- cancel_all_for_person updates all active/pending subscriptions and returns count
- list_by_project pagination
- list_by_person returns all subscriptions
- ClientError wrapping raises RepositoryError

Requirements: 17.2, 19.12
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from src.domain.entities.subscription import Subscription
from src.domain.exceptions import NotFoundError, RepositoryError
from src.domain.value_objects.project_status import SubscriptionStatus
from src.infrastructure.persistence.dynamodb_subscription_repository import (
    DynamoDBSubscriptionRepository,
)

TABLE_NAME = "ugsys-subscriptions-test"


def _create_subscriptions_table(client: Any) -> None:
    """Create the subscriptions DynamoDB table with all GSIs matching production schema."""
    client.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "person_id", "AttributeType": "S"},
            {"AttributeName": "created_at", "AttributeType": "S"},
            {"AttributeName": "project_id", "AttributeType": "S"},
            {"AttributeName": "person_project_key", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "person-index",
                "KeySchema": [
                    {"AttributeName": "person_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "project-index",
                "KeySchema": [
                    {"AttributeName": "project_id", "KeyType": "HASH"},
                    {"AttributeName": "created_at", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "person-project-index",
                "KeySchema": [
                    {"AttributeName": "person_project_key", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _make_subscription(
    *,
    sub_id: str = "01JSUB0000000000000000001",
    project_id: str = "01JPROJ000000000000000001",
    person_id: str = "01JPRSN000000000000000001",
    status: SubscriptionStatus = SubscriptionStatus.PENDING,
    notes: str = "",
    subscription_date: str = "",
    is_active: bool = True,
    created_at: str = "2025-01-15T10:00:00Z",
    updated_at: str = "2025-01-15T10:00:00Z",
    migrated_from: str | None = None,
    migrated_at: str | None = None,
) -> Subscription:
    return Subscription(
        id=sub_id,
        project_id=project_id,
        person_id=person_id,
        status=status,
        notes=notes,
        subscription_date=subscription_date,
        is_active=is_active,
        created_at=created_at,
        updated_at=updated_at,
        migrated_from=migrated_from,
        migrated_at=migrated_at,
    )


class _AsyncDynamoDBClient:
    """Wraps synchronous boto3 client to provide async interface for moto tests."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def put_item(self, **kwargs: Any) -> Any:
        return self._client.put_item(**kwargs)

    async def get_item(self, **kwargs: Any) -> Any:
        return self._client.get_item(**kwargs)

    async def delete_item(self, **kwargs: Any) -> Any:
        return self._client.delete_item(**kwargs)

    async def query(self, **kwargs: Any) -> Any:
        return self._client.query(**kwargs)

    async def scan(self, **kwargs: Any) -> Any:
        return self._client.scan(**kwargs)


@pytest.fixture
def dynamodb_setup():
    """Create moto DynamoDB table with all GSIs and return async client wrapper."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        _create_subscriptions_table(client)
        yield _AsyncDynamoDBClient(client), client


@pytest.fixture
def repo(dynamodb_setup):
    """Return a DynamoDBSubscriptionRepository wired to the moto table."""
    async_client, _ = dynamodb_setup
    return DynamoDBSubscriptionRepository(table_name=TABLE_NAME, client=async_client)


# ── save / find_by_id round-trip ──────────────────────────────────────────────


async def test_save_and_find_by_id_round_trip_all_fields(repo):
    """Round-trip with every field populated, including optional ones."""
    # Arrange
    sub = _make_subscription(
        notes="I want to help with Python workshops",
        subscription_date="2025-01-15T09:00:00Z",
        status=SubscriptionStatus.ACTIVE,
        migrated_from="registry",
        migrated_at="2025-01-10T08:00:00Z",
    )

    # Act
    saved = await repo.save(sub)
    found = await repo.find_by_id(sub.id)

    # Assert
    assert found is not None
    assert found.id == saved.id
    assert found.project_id == "01JPROJ000000000000000001"
    assert found.person_id == "01JPRSN000000000000000001"
    assert found.status == SubscriptionStatus.ACTIVE
    assert found.notes == "I want to help with Python workshops"
    assert found.subscription_date == "2025-01-15T09:00:00Z"
    assert found.is_active is True
    assert found.created_at == "2025-01-15T10:00:00Z"
    assert found.updated_at == "2025-01-15T10:00:00Z"
    assert found.migrated_from == "registry"
    assert found.migrated_at == "2025-01-10T08:00:00Z"


async def test_save_and_find_by_id_minimal_fields(repo):
    """Round-trip with only required fields — optional fields use defaults."""
    # Arrange
    sub = _make_subscription()

    # Act
    await repo.save(sub)
    found = await repo.find_by_id(sub.id)

    # Assert
    assert found is not None
    assert found.id == sub.id
    assert found.status == SubscriptionStatus.PENDING
    assert found.notes == ""
    assert found.subscription_date == ""
    assert found.is_active is True
    assert found.migrated_from is None
    assert found.migrated_at is None


async def test_find_by_id_returns_none_for_nonexistent(repo):
    """find_by_id returns None when the subscription does not exist."""
    result = await repo.find_by_id("01JNONEXISTENT0000000001")
    assert result is None


# ── Backward compatibility — items missing optional fields ────────────────────


async def test_backward_compatibility_missing_optional_fields(dynamodb_setup):
    """Items written without optional fields deserialize with safe defaults."""
    async_client, raw_client = dynamodb_setup

    # Arrange — write a minimal item directly (simulating old data)
    raw_client.put_item(
        TableName=TABLE_NAME,
        Item={
            "PK": {"S": "SUB#01JOLD0000000000000000001"},
            "SK": {"S": "SUB"},
            "id": {"S": "01JOLD0000000000000000001"},
            "project_id": {"S": "01JPROJ000000000000000099"},
            "person_id": {"S": "01JPRSN000000000000000099"},
            "status": {"S": "active"},
            "created_at": {"S": "2024-06-01T00:00:00Z"},
            "updated_at": {"S": "2024-06-01T00:00:00Z"},
            "person_project_key": {"S": "01JPRSN000000000000000099#01JPROJ000000000000000099"},
        },
    )

    repo = DynamoDBSubscriptionRepository(table_name=TABLE_NAME, client=async_client)

    # Act
    found = await repo.find_by_id("01JOLD0000000000000000001")

    # Assert — all optional fields have safe defaults
    assert found is not None
    assert found.status == SubscriptionStatus.ACTIVE
    assert found.notes == ""
    assert found.subscription_date == ""
    assert found.is_active is True
    assert found.migrated_from is None
    assert found.migrated_at is None


# ── Duplicate save raises RepositoryError ─────────────────────────────────────


async def test_duplicate_save_raises_repository_error(repo):
    """Saving a subscription with the same ID twice raises RepositoryError."""
    # Arrange
    sub = _make_subscription()
    await repo.save(sub)

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.save(sub)

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


# ── update ────────────────────────────────────────────────────────────────────


async def test_update_existing_subscription(repo):
    """Updating an existing subscription persists the changes."""
    # Arrange
    sub = _make_subscription()
    await repo.save(sub)
    sub.status = SubscriptionStatus.ACTIVE
    sub.notes = "Updated notes"
    sub.updated_at = "2025-01-16T12:00:00Z"

    # Act
    await repo.update(sub)
    found = await repo.find_by_id(sub.id)

    # Assert
    assert found is not None
    assert found.status == SubscriptionStatus.ACTIVE
    assert found.notes == "Updated notes"
    assert found.updated_at == "2025-01-16T12:00:00Z"


async def test_update_nonexistent_raises_not_found_error(repo):
    """Updating a non-existent subscription raises NotFoundError."""
    # Arrange
    sub = _make_subscription(sub_id="01JNONEXISTENT0000000099")

    # Act + Assert
    with pytest.raises(NotFoundError) as exc_info:
        await repo.update(sub)

    assert exc_info.value.error_code == "NOT_FOUND"
    assert exc_info.value.user_message == "Subscription not found"


# ── find_by_person_and_project via GSI-3 ──────────────────────────────────────


async def test_find_by_person_and_project_returns_correct_subscription(repo):
    """find_by_person_and_project returns the matching non-cancelled subscription via GSI-3."""
    # Arrange
    sub = _make_subscription(
        sub_id="01JSUB0000000000000000010",
        person_id="01JPRSN000000000000000010",
        project_id="01JPROJ000000000000000010",
        status=SubscriptionStatus.ACTIVE,
    )
    await repo.save(sub)

    # Act
    found = await repo.find_by_person_and_project(
        person_id="01JPRSN000000000000000010",
        project_id="01JPROJ000000000000000010",
    )

    # Assert
    assert found is not None
    assert found.id == "01JSUB0000000000000000010"
    assert found.person_id == "01JPRSN000000000000000010"
    assert found.project_id == "01JPROJ000000000000000010"
    assert found.status == SubscriptionStatus.ACTIVE


async def test_find_by_person_and_project_returns_none_when_not_found(repo):
    """find_by_person_and_project returns None when no subscription exists."""
    result = await repo.find_by_person_and_project(
        person_id="01JPRSN000000000000000099",
        project_id="01JPROJ000000000000000099",
    )
    assert result is None


async def test_find_by_person_and_project_skips_cancelled(repo):
    """find_by_person_and_project skips cancelled subscriptions."""
    # Arrange — save a cancelled subscription
    sub = _make_subscription(
        sub_id="01JSUB0000000000000000020",
        person_id="01JPRSN000000000000000020",
        project_id="01JPROJ000000000000000020",
        status=SubscriptionStatus.CANCELLED,
        is_active=False,
    )
    await repo.save(sub)

    # Act
    found = await repo.find_by_person_and_project(
        person_id="01JPRSN000000000000000020",
        project_id="01JPROJ000000000000000020",
    )

    # Assert — cancelled subscription is skipped
    assert found is None


async def test_find_by_person_and_project_returns_non_cancelled_over_cancelled(repo):
    """When both cancelled and active subscriptions exist, returns the active one."""
    # Arrange — save cancelled first, then active
    person_id = "01JPRSN000000000000000030"
    project_id = "01JPROJ000000000000000030"

    cancelled = _make_subscription(
        sub_id="01JSUB0000000000000000030",
        person_id=person_id,
        project_id=project_id,
        status=SubscriptionStatus.CANCELLED,
        is_active=False,
        created_at="2025-01-14T10:00:00Z",
    )
    active = _make_subscription(
        sub_id="01JSUB0000000000000000031",
        person_id=person_id,
        project_id=project_id,
        status=SubscriptionStatus.ACTIVE,
        created_at="2025-01-15T10:00:00Z",
    )
    await repo.save(cancelled)
    await repo.save(active)

    # Act
    found = await repo.find_by_person_and_project(
        person_id=person_id,
        project_id=project_id,
    )

    # Assert — returns the non-cancelled subscription
    assert found is not None
    assert found.status != SubscriptionStatus.CANCELLED


# ── cancel_all_for_person ─────────────────────────────────────────────────────


async def test_cancel_all_for_person_cancels_active_and_pending(repo):
    """cancel_all_for_person updates all active/pending subscriptions and returns count."""
    # Arrange
    person_id = "01JPRSN000000000000000040"
    active_sub = _make_subscription(
        sub_id="01JSUB0000000000000000040",
        person_id=person_id,
        project_id="01JPROJ000000000000000040",
        status=SubscriptionStatus.ACTIVE,
        created_at="2025-01-15T10:00:00Z",
    )
    pending_sub = _make_subscription(
        sub_id="01JSUB0000000000000000041",
        person_id=person_id,
        project_id="01JPROJ000000000000000041",
        status=SubscriptionStatus.PENDING,
        created_at="2025-01-15T11:00:00Z",
    )
    rejected_sub = _make_subscription(
        sub_id="01JSUB0000000000000000042",
        person_id=person_id,
        project_id="01JPROJ000000000000000042",
        status=SubscriptionStatus.REJECTED,
        is_active=False,
        created_at="2025-01-15T12:00:00Z",
    )
    await repo.save(active_sub)
    await repo.save(pending_sub)
    await repo.save(rejected_sub)

    # Act
    cancelled_count = await repo.cancel_all_for_person(person_id)

    # Assert — only active and pending are cancelled (not rejected)
    assert cancelled_count == 2

    # Verify the subscriptions were actually updated in DynamoDB
    found_active = await repo.find_by_id("01JSUB0000000000000000040")
    assert found_active is not None
    assert found_active.status == SubscriptionStatus.CANCELLED
    assert found_active.is_active is False

    found_pending = await repo.find_by_id("01JSUB0000000000000000041")
    assert found_pending is not None
    assert found_pending.status == SubscriptionStatus.CANCELLED
    assert found_pending.is_active is False

    # Rejected subscription should remain unchanged
    found_rejected = await repo.find_by_id("01JSUB0000000000000000042")
    assert found_rejected is not None
    assert found_rejected.status == SubscriptionStatus.REJECTED


async def test_cancel_all_for_person_returns_zero_when_none_cancellable(repo):
    """cancel_all_for_person returns 0 when no active/pending subscriptions exist."""
    # Arrange — only a rejected subscription
    person_id = "01JPRSN000000000000000050"
    rejected_sub = _make_subscription(
        sub_id="01JSUB0000000000000000050",
        person_id=person_id,
        status=SubscriptionStatus.REJECTED,
        is_active=False,
        created_at="2025-01-15T10:00:00Z",
    )
    await repo.save(rejected_sub)

    # Act
    cancelled_count = await repo.cancel_all_for_person(person_id)

    # Assert
    assert cancelled_count == 0


async def test_cancel_all_for_person_returns_zero_for_unknown_person(repo):
    """cancel_all_for_person returns 0 for a person with no subscriptions."""
    cancelled_count = await repo.cancel_all_for_person("01JPRSN_UNKNOWN_00000001")
    assert cancelled_count == 0


# ── list_by_project pagination ────────────────────────────────────────────────


async def test_list_by_project_returns_paginated_results(repo):
    """list_by_project returns paginated subscriptions for a project."""
    # Arrange — create 5 subscriptions for the same project
    project_id = "01JPROJ000000000000000060"
    for i in range(5):
        sub = _make_subscription(
            sub_id=f"01JSUB000000000000000006{i}",
            project_id=project_id,
            person_id=f"01JPRSN00000000000000006{i}",
            created_at=f"2025-01-{15 - i}T10:00:00Z",
        )
        await repo.save(sub)

    # Act — page 1, page_size 2
    page_items, total = await repo.list_by_project(project_id, page=1, page_size=2)

    # Assert
    assert total == 5
    assert len(page_items) == 2


async def test_list_by_project_second_page(repo):
    """list_by_project returns correct items for the second page."""
    # Arrange — create 3 subscriptions
    project_id = "01JPROJ000000000000000070"
    for i in range(3):
        sub = _make_subscription(
            sub_id=f"01JSUB000000000000000007{i}",
            project_id=project_id,
            person_id=f"01JPRSN00000000000000007{i}",
            created_at=f"2025-01-{15 - i}T10:00:00Z",
        )
        await repo.save(sub)

    # Act — page 2, page_size 2
    page_items, total = await repo.list_by_project(project_id, page=2, page_size=2)

    # Assert
    assert total == 3
    assert len(page_items) == 1


async def test_list_by_project_empty_for_unknown_project(repo):
    """list_by_project returns empty list for a project with no subscriptions."""
    page_items, total = await repo.list_by_project("01JPROJ_UNKNOWN_00000001", page=1, page_size=10)
    assert total == 0
    assert page_items == []


# ── list_by_person ────────────────────────────────────────────────────────────


async def test_list_by_person_returns_all_subscriptions(repo):
    """list_by_person returns all subscriptions for a person."""
    # Arrange — create 3 subscriptions for the same person across different projects
    person_id = "01JPRSN000000000000000080"
    for i in range(3):
        sub = _make_subscription(
            sub_id=f"01JSUB000000000000000008{i}",
            person_id=person_id,
            project_id=f"01JPROJ00000000000000008{i}",
            created_at=f"2025-01-{15 - i}T10:00:00Z",
        )
        await repo.save(sub)

    # Act
    subs = await repo.list_by_person(person_id)

    # Assert
    assert len(subs) == 3
    # Verify sorted by created_at descending
    assert subs[0].created_at >= subs[1].created_at >= subs[2].created_at


async def test_list_by_person_empty_for_unknown_person(repo):
    """list_by_person returns empty list for a person with no subscriptions."""
    subs = await repo.list_by_person("01JPRSN_UNKNOWN_00000001")
    assert subs == []


# ── ClientError wrapping raises RepositoryError ──────────────────────────────


async def test_client_error_on_find_by_id_raises_repository_error():
    """ClientError from DynamoDB is wrapped in RepositoryError with safe user_message."""
    # Arrange — create a mock client that raises ClientError
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "InternalServerError", "Message": "Service unavailable"}}
    mock_client.get_item = _make_async_raiser(ClientError(error_response, "GetItem"))
    repo = DynamoDBSubscriptionRepository(table_name=TABLE_NAME, client=mock_client)

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.find_by_id("01JSUB0000000000000000001")

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


async def test_client_error_on_save_non_conditional_raises_repository_error():
    """Non-conditional ClientError on save is wrapped in RepositoryError."""
    # Arrange
    mock_client = MagicMock()
    error_response = {
        "Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Rate exceeded"}
    }
    mock_client.put_item = _make_async_raiser(ClientError(error_response, "PutItem"))
    repo = DynamoDBSubscriptionRepository(table_name=TABLE_NAME, client=mock_client)
    sub = _make_subscription()

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.save(sub)

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


async def test_client_error_on_query_raises_repository_error():
    """ClientError on query (list_by_person) is wrapped in RepositoryError."""
    # Arrange
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "InternalServerError", "Message": "Service unavailable"}}
    mock_client.query = _make_async_raiser(ClientError(error_response, "Query"))
    repo = DynamoDBSubscriptionRepository(table_name=TABLE_NAME, client=mock_client)

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.list_by_person("01JPRSN000000000000000001")

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


async def test_client_error_on_cancel_all_raises_repository_error():
    """ClientError on cancel_all_for_person is wrapped in RepositoryError."""
    # Arrange
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "InternalServerError", "Message": "Service unavailable"}}
    mock_client.query = _make_async_raiser(ClientError(error_response, "Query"))
    repo = DynamoDBSubscriptionRepository(table_name=TABLE_NAME, client=mock_client)

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.cancel_all_for_person("01JPRSN000000000000000001")

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


# ── Helper ────────────────────────────────────────────────────────────────────


def _make_async_raiser(exc: Exception):
    """Create an async function that raises the given exception."""

    async def _raiser(**kwargs: Any) -> None:
        raise exc

    return _raiser
