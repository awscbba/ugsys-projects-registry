"""Integration tests for DynamoDBProjectRepository using moto mock_aws.

Tests cover:
- Table creation with all GSIs matching production schema
- save/find_by_id round-trip for all fields including optional ones
- Backward compatibility: items missing optional fields deserialize with safe defaults
- ConditionalCheckFailedException on duplicate save raises RepositoryError
- list_public returns only active+enabled projects and excludes notification_emails

Requirements: 17.2, 19.12
"""

from __future__ import annotations

from typing import Any

import boto3
import pytest
from moto import mock_aws

from src.domain.entities.form_schema import CustomField, FieldType, FormSchema
from src.domain.entities.project import Project, ProjectImage
from src.domain.exceptions import RepositoryError
from src.domain.value_objects.project_status import ProjectStatus
from src.infrastructure.persistence.dynamodb_project_repository import DynamoDBProjectRepository

TABLE_NAME = "ugsys-projects-test"


def _create_projects_table(client: Any) -> None:
    """Create the projects DynamoDB table with all GSIs matching production schema."""
    client.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
            {"AttributeName": "GSI2PK", "AttributeType": "S"},
            {"AttributeName": "GSI2SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "status-index",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "created_by-index",
                "KeySchema": [
                    {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _make_project(
    *,
    project_id: str = "01JTEST000000000000000001",
    name: str = "Test Project",
    description: str = "A test project description",
    rich_text: str = "",
    category: str = "",
    status: ProjectStatus = ProjectStatus.PENDING,
    is_enabled: bool = False,
    max_participants: int = 50,
    current_participants: int = 0,
    start_date: str = "",
    end_date: str = "",
    created_by: str = "01JOWNER00000000000000001",
    notification_emails: list[str] | None = None,
    enable_subscription_notifications: bool = False,
    images: list[ProjectImage] | None = None,
    form_schema: FormSchema | None = None,
    created_at: str = "2025-01-15T10:00:00Z",
    updated_at: str = "2025-01-15T10:00:00Z",
    migrated_from: str | None = None,
    migrated_at: str | None = None,
) -> Project:
    return Project(
        id=project_id,
        name=name,
        description=description,
        rich_text=rich_text,
        category=category,
        status=status,
        is_enabled=is_enabled,
        max_participants=max_participants,
        current_participants=current_participants,
        start_date=start_date,
        end_date=end_date,
        created_by=created_by,
        notification_emails=notification_emails or [],
        enable_subscription_notifications=enable_subscription_notifications,
        images=images or [],
        form_schema=form_schema,
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
        _create_projects_table(client)
        yield _AsyncDynamoDBClient(client), client


@pytest.fixture
def repo(dynamodb_setup):
    """Return a DynamoDBProjectRepository wired to the moto table."""
    async_client, _ = dynamodb_setup
    return DynamoDBProjectRepository(table_name=TABLE_NAME, client=async_client)


# ── save / find_by_id round-trip — all fields including optional ones ─────────


async def test_save_and_find_by_id_round_trip_all_fields(repo):
    """Round-trip with every field populated, including optional ones."""
    # Arrange
    form_schema = FormSchema(
        fields=[
            CustomField(
                id="field-1",
                field_type=FieldType.TEXT,
                question="What is your name?",
                required=True,
            ),
            CustomField(
                id="field-2",
                field_type=FieldType.POLL_SINGLE,
                question="Preferred language?",
                required=False,
                options=["Python", "TypeScript", "Go"],
            ),
        ]
    )
    images = [
        ProjectImage(
            image_id="01JIMG0000000000000000001",
            filename="banner.jpg",
            content_type="image/jpeg",
            cloudfront_url="https://cdn.cbba.cloud.org.bo/banner.jpg",
            uploaded_at="2025-01-15T09:00:00Z",
        ),
    ]
    project = _make_project(
        rich_text="<p>Extended content</p>",
        category="community",
        status=ProjectStatus.ACTIVE,
        is_enabled=True,
        max_participants=100,
        current_participants=5,
        start_date="2025-02-01T00:00:00Z",
        end_date="2025-06-30T23:59:59Z",
        notification_emails=["admin@example.com", "mod@example.com"],
        enable_subscription_notifications=True,
        images=images,
        form_schema=form_schema,
        migrated_from="registry",
        migrated_at="2025-01-10T08:00:00Z",
    )

    # Act
    saved = await repo.save(project)
    found = await repo.find_by_id(project.id)

    # Assert
    assert found is not None
    assert found.id == saved.id
    assert found.name == "Test Project"
    assert found.description == "A test project description"
    assert found.rich_text == "<p>Extended content</p>"
    assert found.category == "community"
    assert found.status == ProjectStatus.ACTIVE
    assert found.is_enabled is True
    assert found.max_participants == 100
    assert found.current_participants == 5
    assert found.start_date == "2025-02-01T00:00:00Z"
    assert found.end_date == "2025-06-30T23:59:59Z"
    assert found.created_by == "01JOWNER00000000000000001"
    assert sorted(found.notification_emails) == ["admin@example.com", "mod@example.com"]
    assert found.enable_subscription_notifications is True
    assert len(found.images) == 1
    assert found.images[0].image_id == "01JIMG0000000000000000001"
    assert found.images[0].filename == "banner.jpg"
    assert found.images[0].content_type == "image/jpeg"
    assert found.images[0].cloudfront_url == "https://cdn.cbba.cloud.org.bo/banner.jpg"
    assert found.form_schema is not None
    assert len(found.form_schema.fields) == 2
    assert found.form_schema.fields[0].id == "field-1"
    assert found.form_schema.fields[0].field_type == FieldType.TEXT
    assert found.form_schema.fields[0].required is True
    assert found.form_schema.fields[1].options == ["Python", "TypeScript", "Go"]
    assert found.created_at == "2025-01-15T10:00:00Z"
    assert found.updated_at == "2025-01-15T10:00:00Z"
    assert found.migrated_from == "registry"
    assert found.migrated_at == "2025-01-10T08:00:00Z"


async def test_save_and_find_by_id_minimal_fields(repo):
    """Round-trip with only required fields — optional fields use defaults."""
    # Arrange
    project = _make_project()

    # Act
    await repo.save(project)
    found = await repo.find_by_id(project.id)

    # Assert
    assert found is not None
    assert found.id == project.id
    assert found.name == "Test Project"
    assert found.rich_text == ""
    assert found.category == ""
    assert found.start_date == ""
    assert found.end_date == ""
    assert found.notification_emails == []
    assert found.enable_subscription_notifications is False
    assert found.images == []
    assert found.form_schema is None
    assert found.migrated_from is None
    assert found.migrated_at is None


# ── Backward compatibility — items missing optional fields ────────────────────


async def test_backward_compatibility_missing_optional_fields(dynamodb_setup):
    """Items written without optional fields deserialize with safe defaults."""
    async_client, raw_client = dynamodb_setup

    # Arrange — write a minimal item directly (simulating old data without optional attrs)
    raw_client.put_item(
        TableName=TABLE_NAME,
        Item={
            "PK": {"S": "PROJECT#01JOLD0000000000000000001"},
            "SK": {"S": "PROJECT"},
            "id": {"S": "01JOLD0000000000000000001"},
            "name": {"S": "Legacy Project"},
            "description": {"S": "Old project from migration"},
            "status": {"S": "active"},
            "max_participants": {"N": "20"},
            "created_by": {"S": "01JOWNER00000000000000002"},
            "created_at": {"S": "2024-06-01T00:00:00Z"},
            "updated_at": {"S": "2024-06-01T00:00:00Z"},
            "GSI1PK": {"S": "STATUS#active"},
            "GSI1SK": {"S": "2024-06-01T00:00:00Z"},
        },
    )

    repo = DynamoDBProjectRepository(table_name=TABLE_NAME, client=async_client)

    # Act
    found = await repo.find_by_id("01JOLD0000000000000000001")

    # Assert — all optional fields have safe defaults
    assert found is not None
    assert found.name == "Legacy Project"
    assert found.rich_text == ""
    assert found.category == ""
    assert found.is_enabled is False
    assert found.current_participants == 0
    assert found.start_date == ""
    assert found.end_date == ""
    assert found.notification_emails == []
    assert found.enable_subscription_notifications is False
    assert found.images == []
    assert found.form_schema is None
    assert found.migrated_from is None
    assert found.migrated_at is None


# ── ConditionalCheckFailedException on duplicate save ─────────────────────────


async def test_duplicate_save_raises_repository_error(repo):
    """Saving a project with the same ID twice raises RepositoryError."""
    # Arrange
    project = _make_project()
    await repo.save(project)

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.save(project)

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


# ── list_public — only active+enabled, excludes notification_emails ───────────


async def test_list_public_returns_only_active_enabled_projects(repo):
    """list_public returns only projects with status=active AND is_enabled=true."""
    # Arrange — create projects with various status/enabled combinations
    active_enabled = _make_project(
        project_id="01JTEST000000000000000010",
        name="Active Enabled",
        status=ProjectStatus.ACTIVE,
        is_enabled=True,
        notification_emails=["secret@example.com"],
        created_at="2025-01-15T10:00:00Z",
        updated_at="2025-01-15T10:00:00Z",
    )
    active_disabled = _make_project(
        project_id="01JTEST000000000000000011",
        name="Active Disabled",
        status=ProjectStatus.ACTIVE,
        is_enabled=False,
        created_at="2025-01-14T10:00:00Z",
        updated_at="2025-01-14T10:00:00Z",
    )
    pending_enabled = _make_project(
        project_id="01JTEST000000000000000012",
        name="Pending Enabled",
        status=ProjectStatus.PENDING,
        is_enabled=True,
        created_at="2025-01-13T10:00:00Z",
        updated_at="2025-01-13T10:00:00Z",
    )
    completed_project = _make_project(
        project_id="01JTEST000000000000000013",
        name="Completed",
        status=ProjectStatus.COMPLETED,
        is_enabled=False,
        created_at="2025-01-12T10:00:00Z",
        updated_at="2025-01-12T10:00:00Z",
    )

    await repo.save(active_enabled)
    await repo.save(active_disabled)
    await repo.save(pending_enabled)
    await repo.save(completed_project)

    # Act
    public_projects = await repo.list_public(limit=100)

    # Assert — only active+enabled project returned
    assert len(public_projects) == 1
    assert public_projects[0].id == "01JTEST000000000000000010"
    assert public_projects[0].name == "Active Enabled"


async def test_list_public_strips_notification_emails(repo):
    """list_public strips notification_emails from returned projects."""
    # Arrange
    project = _make_project(
        project_id="01JTEST000000000000000020",
        name="Public Project",
        status=ProjectStatus.ACTIVE,
        is_enabled=True,
        notification_emails=["admin@example.com", "notify@example.com"],
    )
    await repo.save(project)

    # Act
    public_projects = await repo.list_public(limit=100)

    # Assert
    assert len(public_projects) == 1
    assert public_projects[0].notification_emails == []


async def test_list_public_respects_limit(repo):
    """list_public respects the limit parameter."""
    # Arrange — create 3 active+enabled projects
    for i in range(3):
        p = _make_project(
            project_id=f"01JTEST00000000000000003{i}",
            name=f"Project {i}",
            status=ProjectStatus.ACTIVE,
            is_enabled=True,
            created_at=f"2025-01-{15 - i}T10:00:00Z",
            updated_at=f"2025-01-{15 - i}T10:00:00Z",
        )
        await repo.save(p)

    # Act
    public_projects = await repo.list_public(limit=2)

    # Assert
    assert len(public_projects) == 2


# ── find_by_id returns None for non-existent project ─────────────────────────


async def test_find_by_id_returns_none_for_nonexistent(repo):
    """find_by_id returns None when the project does not exist."""
    result = await repo.find_by_id("01JNONEXISTENT0000000001")
    assert result is None
