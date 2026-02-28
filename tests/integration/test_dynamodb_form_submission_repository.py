"""Integration tests for DynamoDBFormSubmissionRepository using moto mock_aws.

Tests cover:
- _to_item/_from_item round-trip preserving all responses dict entries
- save/find round-trip with complex responses dict (nested values, lists, etc.)
- find_by_person_and_project returns None when no submission exists
- Duplicate save raises RepositoryError
- list_by_project returns sorted results
- Backward compatibility for items missing optional fields
- Property 12: FormSubmission round-trip (hypothesis)

Requirements: 6.7, 17.2
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from moto import mock_aws

from src.domain.entities.form_submission import FormSubmission
from src.domain.exceptions import RepositoryError
from src.infrastructure.persistence.dynamodb_form_submission_repository import (
    DynamoDBFormSubmissionRepository,
)

TABLE_NAME = "ugsys-form-submissions-test"


def _create_form_submissions_table(client: Any) -> None:
    """Create the form submissions DynamoDB table with all GSIs matching production schema."""
    client.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "project_id", "AttributeType": "S"},
            {"AttributeName": "person_id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "project-index",
                "KeySchema": [
                    {"AttributeName": "project_id", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "person-index",
                "KeySchema": [
                    {"AttributeName": "person_id", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _make_submission(
    *,
    submission_id: str = "01JFSUB000000000000000001",
    project_id: str = "01JPROJ000000000000000001",
    person_id: str = "01JPRSN000000000000000001",
    responses: dict[str, Any] | None = None,
    created_at: str = "2025-01-15T10:00:00Z",
    updated_at: str = "2025-01-15T10:00:00Z",
    migrated_from: str | None = None,
    migrated_at: str | None = None,
) -> FormSubmission:
    return FormSubmission(
        id=submission_id,
        project_id=project_id,
        person_id=person_id,
        responses=responses if responses is not None else {},
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
        _create_form_submissions_table(client)
        yield _AsyncDynamoDBClient(client), client


@pytest.fixture
def repo(dynamodb_setup):
    """Return a DynamoDBFormSubmissionRepository wired to the moto table."""
    async_client, _ = dynamodb_setup
    return DynamoDBFormSubmissionRepository(table_name=TABLE_NAME, client=async_client)


# ── save / find round-trip — _to_item/_from_item preserving all responses ─────


async def test_save_and_find_round_trip_all_fields(repo):
    """Round-trip with every field populated, including optional migration fields."""
    # Arrange
    responses = {"field-1": "Alice", "field-2": "Python", "field-3": ["opt-a", "opt-b"]}
    submission = _make_submission(
        responses=responses,
        migrated_from="registry",
        migrated_at="2025-01-10T08:00:00Z",
    )

    # Act
    saved = await repo.save(submission)
    found = await repo.find_by_person_and_project(
        person_id=submission.person_id, project_id=submission.project_id
    )

    # Assert
    assert found is not None
    assert found.id == saved.id
    assert found.project_id == "01JPROJ000000000000000001"
    assert found.person_id == "01JPRSN000000000000000001"
    assert found.responses == responses
    assert found.responses["field-1"] == "Alice"
    assert found.responses["field-2"] == "Python"
    assert found.responses["field-3"] == ["opt-a", "opt-b"]
    assert found.created_at == "2025-01-15T10:00:00Z"
    assert found.updated_at == "2025-01-15T10:00:00Z"
    assert found.migrated_from == "registry"
    assert found.migrated_at == "2025-01-10T08:00:00Z"


async def test_save_and_find_round_trip_complex_responses(repo):
    """Round-trip with complex responses dict: nested values, lists, numbers, booleans."""
    # Arrange
    complex_responses: dict[str, Any] = {
        "text-field": "Simple answer",
        "number-field": 42,
        "boolean-field": True,
        "list-field": ["option-a", "option-b", "option-c"],
        "nested-field": {"key": "value", "count": 3},
        "empty-string": "",
        "null-value": None,
        "float-field": 3.14,
    }
    submission = _make_submission(
        submission_id="01JFSUB000000000000000002",
        responses=complex_responses,
    )

    # Act
    await repo.save(submission)
    found = await repo.find_by_person_and_project(
        person_id=submission.person_id, project_id=submission.project_id
    )

    # Assert — every entry preserved exactly
    assert found is not None
    assert found.responses == complex_responses
    assert found.responses["text-field"] == "Simple answer"
    assert found.responses["number-field"] == 42
    assert found.responses["boolean-field"] is True
    assert found.responses["list-field"] == ["option-a", "option-b", "option-c"]
    assert found.responses["nested-field"] == {"key": "value", "count": 3}
    assert found.responses["empty-string"] == ""
    assert found.responses["null-value"] is None
    assert found.responses["float-field"] == 3.14


async def test_save_and_find_round_trip_empty_responses(repo):
    """Round-trip with empty responses dict."""
    # Arrange
    submission = _make_submission(
        submission_id="01JFSUB000000000000000003",
        person_id="01JPRSN000000000000000003",
        responses={},
    )

    # Act
    await repo.save(submission)
    found = await repo.find_by_person_and_project(
        person_id="01JPRSN000000000000000003",
        project_id="01JPROJ000000000000000001",
    )

    # Assert
    assert found is not None
    assert found.responses == {}


# ── find_by_person_and_project returns None when no submission exists ─────────


async def test_find_by_person_and_project_returns_none_when_not_found(repo):
    """find_by_person_and_project returns None when no submission exists."""
    result = await repo.find_by_person_and_project(
        person_id="01JPRSN_NONEXISTENT_00001",
        project_id="01JPROJ_NONEXISTENT_00001",
    )
    assert result is None


# ── Duplicate save raises RepositoryError ─────────────────────────────────────


async def test_duplicate_save_raises_repository_error(repo):
    """Saving a submission with the same ID twice raises RepositoryError."""
    # Arrange
    submission = _make_submission()
    await repo.save(submission)

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.save(submission)

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


# ── list_by_project returns sorted results ────────────────────────────────────


async def test_list_by_project_returns_sorted_by_created_at_desc(repo):
    """list_by_project returns submissions sorted by created_at descending."""
    # Arrange — create 3 submissions for the same project with different timestamps
    project_id = "01JPROJ000000000000000010"
    for i, ts in enumerate(
        ["2025-01-13T10:00:00Z", "2025-01-15T10:00:00Z", "2025-01-14T10:00:00Z"]
    ):
        sub = _make_submission(
            submission_id=f"01JFSUB00000000000000001{i}",
            project_id=project_id,
            person_id=f"01JPRSN00000000000000001{i}",
            responses={"q1": f"answer-{i}"},
            created_at=ts,
            updated_at=ts,
        )
        await repo.save(sub)

    # Act
    results = await repo.list_by_project(project_id)

    # Assert — sorted descending by created_at
    assert len(results) == 3
    assert results[0].created_at >= results[1].created_at >= results[2].created_at
    assert results[0].created_at == "2025-01-15T10:00:00Z"
    assert results[2].created_at == "2025-01-13T10:00:00Z"


async def test_list_by_project_empty_for_unknown_project(repo):
    """list_by_project returns empty list for a project with no submissions."""
    results = await repo.list_by_project("01JPROJ_UNKNOWN_00000001")
    assert results == []


# ── Backward compatibility — items missing optional fields ────────────────────


async def test_backward_compatibility_missing_optional_fields(dynamodb_setup):
    """Items written without optional fields deserialize with safe defaults."""
    async_client, raw_client = dynamodb_setup

    # Arrange — write a minimal item directly (simulating old data without optional attrs)
    raw_client.put_item(
        TableName=TABLE_NAME,
        Item={
            "PK": {"S": "SUBMISSION#01JOLD0000000000000000001"},
            "SK": {"S": "SUBMISSION"},
            "id": {"S": "01JOLD0000000000000000001"},
            "project_id": {"S": "01JPROJ000000000000000099"},
            "person_id": {"S": "01JPRSN000000000000000099"},
            # responses, created_at, updated_at, migrated_from, migrated_at all missing
        },
    )

    repo = DynamoDBFormSubmissionRepository(table_name=TABLE_NAME, client=async_client)

    # Act
    found = await repo.find_by_person_and_project(
        person_id="01JPRSN000000000000000099",
        project_id="01JPROJ000000000000000099",
    )

    # Assert — all optional fields have safe defaults
    assert found is not None
    assert found.id == "01JOLD0000000000000000001"
    assert found.project_id == "01JPROJ000000000000000099"
    assert found.person_id == "01JPRSN000000000000000099"
    assert found.responses == {}
    assert found.created_at == ""
    assert found.updated_at == ""
    assert found.migrated_from is None
    assert found.migrated_at is None


# ── ClientError wrapping raises RepositoryError ──────────────────────────────


async def test_client_error_on_save_non_conditional_raises_repository_error():
    """Non-conditional ClientError on save is wrapped in RepositoryError."""
    # Arrange
    mock_client = MagicMock()
    error_response = {
        "Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Rate exceeded"}
    }

    async def _raiser(**kwargs: Any) -> None:
        raise ClientError(error_response, "PutItem")

    mock_client.put_item = _raiser
    repo = DynamoDBFormSubmissionRepository(table_name=TABLE_NAME, client=mock_client)
    submission = _make_submission()

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.save(submission)

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


async def test_client_error_on_query_raises_repository_error():
    """ClientError on query (list_by_project) is wrapped in RepositoryError."""
    # Arrange
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "InternalServerError", "Message": "Service unavailable"}}

    async def _raiser(**kwargs: Any) -> None:
        raise ClientError(error_response, "Query")

    mock_client.query = _raiser
    repo = DynamoDBFormSubmissionRepository(table_name=TABLE_NAME, client=mock_client)

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.list_by_project("01JPROJ000000000000000001")

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


async def test_client_error_on_find_by_person_and_project_raises_repository_error():
    """ClientError on find_by_person_and_project is wrapped in RepositoryError."""
    # Arrange
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "InternalServerError", "Message": "Service unavailable"}}

    async def _raiser(**kwargs: Any) -> None:
        raise ClientError(error_response, "Query")

    mock_client.query = _raiser
    repo = DynamoDBFormSubmissionRepository(table_name=TABLE_NAME, client=mock_client)

    # Act + Assert
    with pytest.raises(RepositoryError) as exc_info:
        await repo.find_by_person_and_project(
            "01JPRSN000000000000000001", "01JPROJ000000000000000001"
        )

    assert exc_info.value.error_code == "REPOSITORY_ERROR"
    assert exc_info.value.user_message == "An unexpected error occurred"


# ── Property 12: FormSubmission round-trip (hypothesis) ───────────────────────
# Feature: projects-registry, Property 12: FormSubmission round-trip
# **Validates: Requirements 6.7**


def _ulid_strategy() -> st.SearchStrategy[str]:
    """Generate ULID-like strings (26 alphanumeric chars)."""
    return st.text(
        alphabet="0123456789ABCDEFGHJKMNPQRSTVWXYZ",
        min_size=26,
        max_size=26,
    )


def _responses_strategy() -> st.SearchStrategy[dict[str, Any]]:
    """Generate realistic form submission responses dicts."""
    response_value = st.one_of(
        st.text(min_size=0, max_size=50),
        st.integers(min_value=-100, max_value=100),
        st.booleans(),
        st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=3),
        st.none(),
    )
    return st.dictionaries(
        keys=st.from_regex(r"[a-z][a-z0-9\-]{0,9}", fullmatch=True),
        values=response_value,
        min_size=0,
        max_size=10,
    )


@given(
    submission_id=_ulid_strategy(),
    project_id=_ulid_strategy(),
    person_id=_ulid_strategy(),
    responses=_responses_strategy(),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
async def test_form_submission_round_trip_property(
    submission_id: str,
    project_id: str,
    person_id: str,
    responses: dict[str, Any],
) -> None:
    """Property 12: For any valid form submission, saving and retrieving it
    must return an equivalent FormSubmission with all responses preserved."""
    with mock_aws():
        client = boto3.client("dynamodb", region_name="us-east-1")
        _create_form_submissions_table(client)
        async_client = _AsyncDynamoDBClient(client)
        repo = DynamoDBFormSubmissionRepository(table_name=TABLE_NAME, client=async_client)

        submission = FormSubmission(
            id=submission_id,
            project_id=project_id,
            person_id=person_id,
            responses=responses,
            created_at="2025-01-15T10:00:00Z",
            updated_at="2025-01-15T10:00:00Z",
        )

        # Act — save and retrieve
        await repo.save(submission)
        found = await repo.find_by_person_and_project(person_id=person_id, project_id=project_id)

        # Assert — round-trip preserves all data
        assert found is not None
        assert found.id == submission_id
        assert found.project_id == project_id
        assert found.person_id == person_id
        assert found.responses == responses
        assert found.created_at == "2025-01-15T10:00:00Z"
        assert found.updated_at == "2025-01-15T10:00:00Z"
