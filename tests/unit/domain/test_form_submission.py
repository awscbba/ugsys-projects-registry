"""Unit tests for FormSubmission domain entity.

Validates: Requirements 6.8, 17.1

Tests cover:
- Creation with required fields — verify defaults
- Creation with all fields populated
- Responses dict can hold various value types
- Equality and inequality
- Responses dict is independent per instance
"""

from src.domain.entities.form_submission import FormSubmission


class TestFormSubmissionCreationDefaults:
    """Tests for FormSubmission creation with required fields — verify defaults."""

    def _make_minimal(self) -> FormSubmission:
        return FormSubmission(id="01JFSUB", project_id="01JPROJ", person_id="01JPERSON")

    def test_responses_defaults_to_empty_dict(self) -> None:
        sub = self._make_minimal()
        assert sub.responses == {}

    def test_created_at_defaults_to_empty(self) -> None:
        sub = self._make_minimal()
        assert sub.created_at == ""

    def test_updated_at_defaults_to_empty(self) -> None:
        sub = self._make_minimal()
        assert sub.updated_at == ""

    def test_migrated_from_defaults_to_none(self) -> None:
        sub = self._make_minimal()
        assert sub.migrated_from is None

    def test_migrated_at_defaults_to_none(self) -> None:
        sub = self._make_minimal()
        assert sub.migrated_at is None

    def test_required_fields_are_set(self) -> None:
        sub = self._make_minimal()
        assert sub.id == "01JFSUB"
        assert sub.project_id == "01JPROJ"
        assert sub.person_id == "01JPERSON"


class TestFormSubmissionCreationAllFields:
    """Tests for FormSubmission creation with all fields populated."""

    def test_creation_with_all_fields(self) -> None:
        sub = FormSubmission(
            id="01JFSUB",
            project_id="01JPROJ",
            person_id="01JPERSON",
            responses={"f1": "Alice", "f2": "Option A"},
            created_at="2025-03-01T10:00:00Z",
            updated_at="2025-03-02T12:00:00Z",
            migrated_from="registry",
            migrated_at="2025-01-10T08:00:00Z",
        )
        assert sub.id == "01JFSUB"
        assert sub.project_id == "01JPROJ"
        assert sub.person_id == "01JPERSON"
        assert sub.responses == {"f1": "Alice", "f2": "Option A"}
        assert sub.created_at == "2025-03-01T10:00:00Z"
        assert sub.updated_at == "2025-03-02T12:00:00Z"
        assert sub.migrated_from == "registry"
        assert sub.migrated_at == "2025-01-10T08:00:00Z"


class TestFormSubmissionResponsesVariousTypes:
    """Tests for responses dict holding various value types."""

    def test_string_values(self) -> None:
        sub = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={"name": "Alice", "city": "Cochabamba"},
        )
        assert sub.responses["name"] == "Alice"
        assert sub.responses["city"] == "Cochabamba"

    def test_list_values(self) -> None:
        sub = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={"skills": ["Python", "AWS", "Docker"]},
        )
        assert sub.responses["skills"] == ["Python", "AWS", "Docker"]

    def test_numeric_values(self) -> None:
        sub = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={"age": 25, "rating": 4.5},
        )
        assert sub.responses["age"] == 25
        assert sub.responses["rating"] == 4.5

    def test_boolean_values(self) -> None:
        sub = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={"agree_terms": True, "has_experience": False},
        )
        assert sub.responses["agree_terms"] is True
        assert sub.responses["has_experience"] is False

    def test_mixed_value_types(self) -> None:
        sub = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={
                "name": "Alice",
                "skills": ["Python", "AWS"],
                "years_exp": 3,
                "available": True,
            },
        )
        assert len(sub.responses) == 4
        assert isinstance(sub.responses["name"], str)
        assert isinstance(sub.responses["skills"], list)
        assert isinstance(sub.responses["years_exp"], int)
        assert isinstance(sub.responses["available"], bool)


class TestFormSubmissionEquality:
    """Tests for FormSubmission equality and inequality."""

    def test_equality_with_same_values(self) -> None:
        a = FormSubmission(id="01JF", project_id="01JP", person_id="01JPER")
        b = FormSubmission(id="01JF", project_id="01JP", person_id="01JPER")
        assert a == b

    def test_equality_with_same_responses(self) -> None:
        a = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={"f1": "val"},
        )
        b = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={"f1": "val"},
        )
        assert a == b

    def test_inequality_with_different_id(self) -> None:
        a = FormSubmission(id="01JF1", project_id="01JP", person_id="01JPER")
        b = FormSubmission(id="01JF2", project_id="01JP", person_id="01JPER")
        assert a != b

    def test_inequality_with_different_responses(self) -> None:
        a = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={"f1": "A"},
        )
        b = FormSubmission(
            id="01JF",
            project_id="01JP",
            person_id="01JPER",
            responses={"f1": "B"},
        )
        assert a != b

    def test_inequality_with_different_project_id(self) -> None:
        a = FormSubmission(id="01JF", project_id="01JP1", person_id="01JPER")
        b = FormSubmission(id="01JF", project_id="01JP2", person_id="01JPER")
        assert a != b


class TestFormSubmissionResponsesIndependence:
    """Tests for responses dict being independent per instance."""

    def test_responses_independent_between_instances(self) -> None:
        a = FormSubmission(id="01JFA", project_id="01JP", person_id="01JPER")
        b = FormSubmission(id="01JFB", project_id="01JP", person_id="01JPER")
        a.responses["name"] = "Alice"
        assert "name" not in b.responses
        assert len(b.responses) == 0

    def test_modifying_responses_does_not_affect_other_instance(self) -> None:
        a = FormSubmission(
            id="01JFA",
            project_id="01JP",
            person_id="01JPER",
            responses={"f1": "shared"},
        )
        b = FormSubmission(id="01JFB", project_id="01JP", person_id="01JPER")
        a.responses["f2"] = "extra"
        assert "f2" not in b.responses
        assert len(a.responses) == 2
        assert len(b.responses) == 0
