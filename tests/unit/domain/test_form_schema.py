"""Unit tests for FormSchema, CustomField, and FieldType domain entities.

Validates: Requirements 5.2, 5.3, 5.4, 17.1
"""

from dataclasses import fields as dataclass_fields
from enum import StrEnum

from src.domain.entities.form_schema import CustomField, FieldType, FormSchema


class TestFieldType:
    """Tests for FieldType StrEnum."""

    def test_is_str_enum(self) -> None:
        assert issubclass(FieldType, StrEnum)

    def test_has_six_members(self) -> None:
        assert len(FieldType) == 6

    def test_text_value(self) -> None:
        assert FieldType.TEXT == "text"

    def test_textarea_value(self) -> None:
        assert FieldType.TEXTAREA == "textarea"

    def test_poll_single_value(self) -> None:
        assert FieldType.POLL_SINGLE == "poll_single"

    def test_poll_multiple_value(self) -> None:
        assert FieldType.POLL_MULTIPLE == "poll_multiple"

    def test_date_value(self) -> None:
        assert FieldType.DATE == "date"

    def test_number_value(self) -> None:
        assert FieldType.NUMBER == "number"

    def test_construction_from_string(self) -> None:
        assert FieldType("text") is FieldType.TEXT
        assert FieldType("poll_single") is FieldType.POLL_SINGLE


class TestCustomField:
    """Tests for CustomField dataclass."""

    def test_valid_text_field(self) -> None:
        field = CustomField(id="f1", field_type=FieldType.TEXT, question="Your name?")
        assert field.id == "f1"
        assert field.field_type == FieldType.TEXT
        assert field.question == "Your name?"

    def test_defaults_required_false(self) -> None:
        field = CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")
        assert field.required is False

    def test_defaults_options_empty_list(self) -> None:
        field = CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")
        assert field.options == []

    def test_all_field_types_constructable(self) -> None:
        for ft in FieldType:
            field = CustomField(id=f"f-{ft.value}", field_type=ft, question=f"Q for {ft}?")
            assert field.field_type == ft

    def test_poll_single_with_options(self) -> None:
        field = CustomField(
            id="poll1",
            field_type=FieldType.POLL_SINGLE,
            question="Favorite color?",
            options=["Red", "Blue", "Green"],
        )
        assert field.options == ["Red", "Blue", "Green"]

    def test_poll_multiple_with_options(self) -> None:
        field = CustomField(
            id="poll2",
            field_type=FieldType.POLL_MULTIPLE,
            question="Select skills",
            required=True,
            options=["Python", "AWS", "Docker", "K8s"],
        )
        assert field.required is True
        assert len(field.options) == 4

    def test_equality_same_values(self) -> None:
        a = CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")
        b = CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")
        assert a == b

    def test_inequality_different_id(self) -> None:
        a = CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")
        b = CustomField(id="f2", field_type=FieldType.TEXT, question="Q?")
        assert a != b

    def test_fields_are_mutable(self) -> None:
        field = CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")
        field.question = "Updated?"
        assert field.question == "Updated?"
        field.required = True
        assert field.required is True
        field.options = ["A", "B"]
        assert field.options == ["A", "B"]


class TestFormSchema:
    """Tests for FormSchema dataclass."""

    def test_defaults_fields_empty_list(self) -> None:
        schema = FormSchema()
        assert schema.fields == []

    def test_construction_with_fields(self) -> None:
        f1 = CustomField(id="f1", field_type=FieldType.TEXT, question="Name?")
        f2 = CustomField(id="f2", field_type=FieldType.NUMBER, question="Age?")
        schema = FormSchema(fields=[f1, f2])
        assert len(schema.fields) == 2
        assert schema.fields[0].id == "f1"
        assert schema.fields[1].id == "f2"

    def test_holds_up_to_20_fields(self) -> None:
        fields = [
            CustomField(id=f"f{i}", field_type=FieldType.TEXT, question=f"Q{i}?") for i in range(20)
        ]
        schema = FormSchema(fields=fields)
        assert len(schema.fields) == 20

    def test_poll_fields_with_options_in_schema(self) -> None:
        poll = CustomField(
            id="p1",
            field_type=FieldType.POLL_SINGLE,
            question="Pick one",
            options=["A", "B", "C"],
        )
        text = CustomField(id="t1", field_type=FieldType.TEXT, question="Comment?")
        schema = FormSchema(fields=[poll, text])
        assert schema.fields[0].options == ["A", "B", "C"]
        assert schema.fields[1].options == []

    def test_equality_same_fields(self) -> None:
        f1 = CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")
        a = FormSchema(fields=[f1])
        b = FormSchema(fields=[CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")])
        assert a == b

    def test_inequality_different_fields(self) -> None:
        a = FormSchema(fields=[CustomField(id="f1", field_type=FieldType.TEXT, question="Q?")])
        b = FormSchema(fields=[CustomField(id="f2", field_type=FieldType.TEXT, question="Q?")])
        assert a != b

    def test_empty_schemas_are_equal(self) -> None:
        assert FormSchema() == FormSchema()

    def test_fields_are_mutable(self) -> None:
        schema = FormSchema()
        new_field = CustomField(id="f1", field_type=FieldType.DATE, question="When?")
        schema.fields.append(new_field)
        assert len(schema.fields) == 1
        assert schema.fields[0].id == "f1"

    def test_fields_list_is_independent_per_instance(self) -> None:
        a = FormSchema()
        b = FormSchema()
        a.fields.append(CustomField(id="f1", field_type=FieldType.TEXT, question="Q?"))
        assert len(b.fields) == 0

    def test_has_fields_attribute(self) -> None:
        dc_fields = {f.name for f in dataclass_fields(FormSchema)}
        assert "fields" in dc_fields
