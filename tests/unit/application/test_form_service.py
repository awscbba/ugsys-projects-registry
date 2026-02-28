"""Unit tests for FormService application service.

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5,
           6.6, 6.7, 17.1, 17.3, 17.5, 17.6

Tests cover:
- update_schema with 21 fields raises ValidationError(FORM_SCHEMA_TOO_MANY_FIELDS)
- update_schema with duplicate field IDs raises ValidationError(FORM_SCHEMA_DUPLICATE_FIELD_IDS)
- update_schema poll field with 1 option raises ValidationError(FORM_SCHEMA_INVALID_OPTIONS)
- update_schema poll field with 11 options raises ValidationError(FORM_SCHEMA_INVALID_OPTIONS)
- update_schema happy path: project_repo.update called once
- update_schema by non-owner non-admin raises AuthorizationError(FORBIDDEN)
- submit missing required field raises ValidationError(FORM_SUBMISSION_MISSING_REQUIRED_FIELD)
- submit invalid poll_single value raises ValidationError(FORM_SUBMISSION_INVALID_RESPONSE)
- submit for project with no schema raises ValidationError(PROJECT_HAS_NO_FORM_SCHEMA)
- submit happy path: form_submission_repo.save called once, correct project_id and person_id
- Property 1: FormSchema serialization round-trip (hypothesis)
- Property 9: FormSchema validation — field count (hypothesis)
- Property 10: FormSchema validation — poll options (hypothesis)
- Property 11: FormSubmission validation (hypothesis)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from src.application.commands.form_commands import SubmitFormCommand, UpdateFormSchemaCommand
from src.application.services.form_service import FormService
from src.domain.entities.form_schema import CustomField, FieldType, FormSchema
from src.domain.entities.form_submission import FormSubmission
from src.domain.entities.project import Project
from src.domain.exceptions import AuthorizationError, ValidationError
from src.domain.repositories.form_submission_repository import FormSubmissionRepository
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.value_objects.project_status import ProjectStatus

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_text_field(
    id: str = "field-1",
    question: str = "Q?",
    required: bool = False,
) -> CustomField:
    """Factory for a valid text CustomField."""
    return CustomField(id=id, field_type=FieldType.TEXT, question=question, required=required)


def make_poll_field(
    id: str = "poll-1",
    options: list[str] | None = None,
    field_type: FieldType = FieldType.POLL_SINGLE,
    required: bool = False,
) -> CustomField:
    """Factory for a valid poll CustomField."""
    return CustomField(
        id=id,
        field_type=field_type,
        question="Pick one",
        required=required,
        options=options if options is not None else ["A", "B"],
    )


def make_project_with_schema(fields: list[CustomField]) -> Project:
    """Factory for a Project with a FormSchema containing the given fields."""
    return Project(
        id="01JPROJ",
        name="Test Project",
        description="A test project",
        created_by="owner",
        status=ProjectStatus.ACTIVE,
        max_participants=10,
        form_schema=FormSchema(fields=fields),
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def make_project_no_schema() -> Project:
    """Factory for a Project without a FormSchema."""
    return Project(
        id="01JPROJ",
        name="Test Project",
        description="A test project",
        created_by="owner",
        status=ProjectStatus.ACTIVE,
        max_participants=10,
        form_schema=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def make_update_schema_cmd(
    project_id: str = "01JPROJ",
    requester_id: str = "owner",
    is_admin: bool = False,
    fields: list[CustomField] | None = None,
) -> UpdateFormSchemaCommand:
    """Factory for an UpdateFormSchemaCommand."""
    return UpdateFormSchemaCommand(
        project_id=project_id,
        requester_id=requester_id,
        is_admin=is_admin,
        fields=fields if fields is not None else [],
    )


def make_service(
    project_repo: ProjectRepository | None = None,
    form_submission_repo: FormSubmissionRepository | None = None,
) -> FormService:
    """Factory for a FormService with mocked repositories."""
    return FormService(
        project_repo=project_repo or AsyncMock(spec=ProjectRepository),
        form_submission_repo=form_submission_repo or AsyncMock(spec=FormSubmissionRepository),
    )


# ── update_schema tests ───────────────────────────────────────────────────────


class TestUpdateSchemaFieldCountValidation:
    """Tests for field count validation in update_schema."""

    @pytest.mark.asyncio
    async def test_update_schema_with_21_fields_raises_too_many_fields(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project_no_schema()
        service = make_service(project_repo=project_repo)
        fields = [make_text_field(id=f"field-{i}", question=f"Q{i}?") for i in range(21)]
        cmd = make_update_schema_cmd(fields=fields)

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.update_schema(cmd)

        assert exc_info.value.error_code == "FORM_SCHEMA_TOO_MANY_FIELDS"

    @pytest.mark.asyncio
    async def test_update_schema_with_duplicate_field_ids_raises_duplicate_ids(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project_no_schema()
        service = make_service(project_repo=project_repo)
        fields = [
            make_text_field(id="dup-id", question="First?"),
            make_text_field(id="dup-id", question="Second?"),
        ]
        cmd = make_update_schema_cmd(fields=fields)

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.update_schema(cmd)

        assert exc_info.value.error_code == "FORM_SCHEMA_DUPLICATE_FIELD_IDS"


class TestUpdateSchemaPollOptionValidation:
    """Tests for poll option count validation in update_schema."""

    @pytest.mark.asyncio
    async def test_update_schema_poll_field_with_1_option_raises_invalid_options(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project_no_schema()
        service = make_service(project_repo=project_repo)
        fields = [make_poll_field(id="poll-1", options=["OnlyOne"])]
        cmd = make_update_schema_cmd(fields=fields)

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.update_schema(cmd)

        assert exc_info.value.error_code == "FORM_SCHEMA_INVALID_OPTIONS"

    @pytest.mark.asyncio
    async def test_update_schema_poll_field_with_11_options_raises_invalid_options(self) -> None:
        # Arrange
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = make_project_no_schema()
        service = make_service(project_repo=project_repo)
        fields = [make_poll_field(id="poll-1", options=[f"opt-{i}" for i in range(11)])]
        cmd = make_update_schema_cmd(fields=fields)

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.update_schema(cmd)

        assert exc_info.value.error_code == "FORM_SCHEMA_INVALID_OPTIONS"


class TestUpdateSchemaHappyPath:
    """Tests for the happy path of update_schema."""

    @pytest.mark.asyncio
    async def test_update_schema_happy_path(self) -> None:
        # Arrange
        project = make_project_no_schema()
        updated_project = make_project_with_schema(
            [make_text_field(id="f1"), make_text_field(id="f2")]
        )
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = project
        project_repo.update.return_value = updated_project
        service = make_service(project_repo=project_repo)
        fields = [
            make_text_field(id="f1", question="Q1?"),
            make_text_field(id="f2", question="Q2?"),
        ]
        cmd = make_update_schema_cmd(fields=fields)

        # Act
        result = await service.update_schema(cmd)

        # Assert
        project_repo.update.assert_called_once()
        assert result.id == updated_project.id


class TestUpdateSchemaAuthorization:
    """Tests for authorization checks in update_schema."""

    @pytest.mark.asyncio
    async def test_update_schema_by_non_owner_non_admin_raises_forbidden(self) -> None:
        # Arrange
        project = make_project_no_schema()  # created_by="owner"
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = project
        service = make_service(project_repo=project_repo)
        cmd = make_update_schema_cmd(requester_id="other-user", is_admin=False, fields=[])

        # Act + Assert
        with pytest.raises(AuthorizationError) as exc_info:
            await service.update_schema(cmd)

        assert exc_info.value.error_code == "FORBIDDEN"
        assert "other-user" not in exc_info.value.user_message


# ── submit tests ──────────────────────────────────────────────────────────────


class TestSubmitValidation:
    """Tests for validation in submit."""

    @pytest.mark.asyncio
    async def test_submit_missing_required_field_raises_missing_required(self) -> None:
        # Arrange
        required_field = make_text_field(id="req-field", question="Required Q?", required=True)
        project = make_project_with_schema([required_field])
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = project
        service = make_service(project_repo=project_repo)
        cmd = SubmitFormCommand(
            project_id="01JPROJ",
            person_id="01JPERSON",
            responses={},  # missing required field
        )

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.submit(cmd)

        assert exc_info.value.error_code == "FORM_SUBMISSION_MISSING_REQUIRED_FIELD"

    @pytest.mark.asyncio
    async def test_submit_invalid_poll_single_value_raises_invalid_response(self) -> None:
        # Arrange
        poll_field = make_poll_field(id="poll-1", options=["A", "B"])
        project = make_project_with_schema([poll_field])
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = project
        service = make_service(project_repo=project_repo)
        cmd = SubmitFormCommand(
            project_id="01JPROJ",
            person_id="01JPERSON",
            responses={"poll-1": "C"},  # "C" not in ["A", "B"]
        )

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.submit(cmd)

        assert exc_info.value.error_code == "FORM_SUBMISSION_INVALID_RESPONSE"

    @pytest.mark.asyncio
    async def test_submit_for_project_with_no_schema_raises_no_schema(self) -> None:
        # Arrange
        project = make_project_no_schema()
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = project
        service = make_service(project_repo=project_repo)
        cmd = SubmitFormCommand(
            project_id="01JPROJ",
            person_id="01JPERSON",
            responses={"field-1": "some answer"},
        )

        # Act + Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.submit(cmd)

        assert exc_info.value.error_code == "PROJECT_HAS_NO_FORM_SCHEMA"


class TestSubmitHappyPath:
    """Tests for the happy path of submit."""

    @pytest.mark.asyncio
    async def test_submit_happy_path(self) -> None:
        # Arrange
        text_field = make_text_field(id="f1", question="Tell us about yourself?", required=False)
        project = make_project_with_schema([text_field])
        project_repo = AsyncMock(spec=ProjectRepository)
        project_repo.find_by_id.return_value = project

        saved_submission = FormSubmission(
            id="01JSUB",
            project_id="01JPROJ",
            person_id="01JPERSON",
            responses={"f1": "My answer"},
            created_at="2026-01-01T00:00:00+00:00",
            updated_at="2026-01-01T00:00:00+00:00",
        )
        form_submission_repo = AsyncMock(spec=FormSubmissionRepository)
        form_submission_repo.save.return_value = saved_submission
        service = make_service(
            project_repo=project_repo,
            form_submission_repo=form_submission_repo,
        )
        cmd = SubmitFormCommand(
            project_id="01JPROJ",
            person_id="01JPERSON",
            responses={"f1": "My answer"},
        )

        # Act
        result = await service.submit(cmd)

        # Assert
        form_submission_repo.save.assert_called_once()
        assert result.project_id == "01JPROJ"
        assert result.person_id == "01JPERSON"


# ── Property-based tests ──────────────────────────────────────────────────────


# Strategies for generating valid form schema components

_FIELD_TYPES_NON_POLL = [FieldType.TEXT, FieldType.TEXTAREA, FieldType.DATE, FieldType.NUMBER]
_FIELD_TYPES_POLL = [FieldType.POLL_SINGLE, FieldType.POLL_MULTIPLE]


@st.composite
def poll_field_strategy(draw: st.DrawFn, field_id: str) -> CustomField:
    """Generate a valid poll CustomField with 2-10 unique options."""
    field_type = draw(st.sampled_from(_FIELD_TYPES_POLL))
    n_options = draw(st.integers(min_value=2, max_value=10))
    options = draw(
        st.lists(
            st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L",))),
            min_size=n_options,
            max_size=n_options,
            unique=True,
        )
    )
    question = draw(
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "P")))
    )
    required = draw(st.booleans())
    return CustomField(
        id=field_id,
        field_type=field_type,
        question=question,
        required=required,
        options=options,
    )


@st.composite
def non_poll_field_strategy(draw: st.DrawFn, field_id: str) -> CustomField:
    """Generate a valid non-poll CustomField."""
    field_type = draw(st.sampled_from(_FIELD_TYPES_NON_POLL))
    question = draw(
        st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "P")))
    )
    required = draw(st.booleans())
    return CustomField(
        id=field_id,
        field_type=field_type,
        question=question,
        required=required,
        options=[],
    )


@st.composite
def form_schema_strategy(draw: st.DrawFn) -> FormSchema:
    """Generate a valid FormSchema with 0-20 fields, unique IDs, valid poll options.

    **Validates: Requirements 5.2, 5.3, 5.4**
    """
    n_fields = draw(st.integers(min_value=0, max_value=20))
    fields: list[CustomField] = []
    for i in range(n_fields):
        field_id = f"field-{i}"
        is_poll = draw(st.booleans())
        if is_poll:
            field = draw(poll_field_strategy(field_id=field_id))
        else:
            field = draw(non_poll_field_strategy(field_id=field_id))
        fields.append(field)
    return FormSchema(fields=fields)


def _schema_to_dict(schema: FormSchema) -> list[dict[str, Any]]:
    """Serialize a FormSchema to a list of dicts (mirrors FormService logic)."""
    return [
        {
            "id": f.id,
            "field_type": f.field_type,
            "question": f.question,
            "required": f.required,
            "options": f.options,
        }
        for f in schema.fields
    ]


def _schema_from_dict(data: list[dict[str, Any]]) -> FormSchema:
    """Deserialize a list of dicts back to a FormSchema."""
    fields = [
        CustomField(
            id=d["id"],
            field_type=FieldType(d["field_type"]),
            question=d["question"],
            required=d["required"],
            options=d["options"],
        )
        for d in data
    ]
    return FormSchema(fields=fields)


@given(form_schema_strategy())
@settings(max_examples=200)
def test_property_1_form_schema_serialization_round_trip(schema: FormSchema) -> None:
    """Property 1: FormSchema serialization round-trip.

    **Validates: Requirements 6.9, 17.5**

    Serialize a valid FormSchema to JSON dict and reconstruct it.
    The reconstructed schema must equal the original.
    """
    # Serialize
    data = _schema_to_dict(schema)
    json_str = json.dumps(data)

    # Deserialize
    parsed = json.loads(json_str)
    reconstructed = _schema_from_dict(parsed)

    # Assert round-trip equality
    assert len(reconstructed.fields) == len(schema.fields)
    for original_field, reconstructed_field in zip(
        schema.fields, reconstructed.fields, strict=True
    ):
        assert reconstructed_field.id == original_field.id
        assert reconstructed_field.field_type == original_field.field_type
        assert reconstructed_field.question == original_field.question
        assert reconstructed_field.required == original_field.required
        assert reconstructed_field.options == original_field.options


@given(st.integers(min_value=21, max_value=30))
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property_9_form_schema_validation_field_count(n_fields: int) -> None:
    """Property 9: FormSchema validation — field count.

    **Validates: Requirements 5.2, 17.5**

    Any field list with more than 20 fields must raise
    ValidationError(FORM_SCHEMA_TOO_MANY_FIELDS).
    """
    # Arrange
    project_repo = AsyncMock(spec=ProjectRepository)
    project_repo.find_by_id.return_value = make_project_no_schema()
    service = make_service(project_repo=project_repo)
    fields = [make_text_field(id=f"field-{i}", question=f"Q{i}?") for i in range(n_fields)]
    cmd = make_update_schema_cmd(fields=fields)

    # Act + Assert
    with pytest.raises(ValidationError) as exc_info:
        await service.update_schema(cmd)

    assert exc_info.value.error_code == "FORM_SCHEMA_TOO_MANY_FIELDS"


@given(
    st.one_of(
        st.integers(min_value=0, max_value=1),  # too few: 0 or 1
        st.integers(min_value=11, max_value=20),  # too many: 11-20
    )
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_property_10_form_schema_validation_poll_options(n_options: int) -> None:
    """Property 10: FormSchema validation — poll options.

    **Validates: Requirements 5.4, 17.5**

    Poll fields with fewer than 2 or more than 10 options must raise
    ValidationError(FORM_SCHEMA_INVALID_OPTIONS).
    """
    # Arrange
    project_repo = AsyncMock(spec=ProjectRepository)
    project_repo.find_by_id.return_value = make_project_no_schema()
    service = make_service(project_repo=project_repo)
    options = [f"opt-{i}" for i in range(n_options)]
    fields = [make_poll_field(id="poll-1", options=options)]
    cmd = make_update_schema_cmd(fields=fields)

    # Act + Assert
    with pytest.raises(ValidationError) as exc_info:
        await service.update_schema(cmd)

    assert exc_info.value.error_code == "FORM_SCHEMA_INVALID_OPTIONS"


@given(
    st.lists(
        st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L",))),
        min_size=1,
        max_size=5,
        unique=True,
    )
)
@settings(max_examples=100)
@pytest.mark.asyncio
async def test_property_11_form_submission_validation_missing_required(
    required_field_ids: list[str],
) -> None:
    """Property 11: FormSubmission validation — missing required fields.

    **Validates: Requirements 6.3, 17.6**

    Submitting a form without providing values for required fields must always
    raise ValidationError(FORM_SUBMISSION_MISSING_REQUIRED_FIELD).
    """
    # Arrange — build a schema with all fields required
    fields = [
        make_text_field(id=fid, question=f"Q for {fid}?", required=True)
        for fid in required_field_ids
    ]
    project = make_project_with_schema(fields)
    project_repo = AsyncMock(spec=ProjectRepository)
    project_repo.find_by_id.return_value = project
    service = make_service(project_repo=project_repo)

    # Submit with empty responses — all required fields are missing
    cmd = SubmitFormCommand(
        project_id="01JPROJ",
        person_id="01JPERSON",
        responses={},
    )

    # Act + Assert
    with pytest.raises(ValidationError) as exc_info:
        await service.submit(cmd)

    assert exc_info.value.error_code == "FORM_SUBMISSION_MISSING_REQUIRED_FIELD"
