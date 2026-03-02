"""Property 1: FormSchema serialization round-trip.

Validates: Requirements 6.9, 17.5
"""

from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from src.domain.entities.form_schema import CustomField, FieldType, FormSchema


def field_type_strategy() -> st.SearchStrategy[FieldType]:
    return st.sampled_from(list(FieldType))


def custom_field_strategy() -> st.SearchStrategy[CustomField]:
    return st.fixed_dictionaries(
        {
            "id": st.text(
                min_size=1,
                max_size=50,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd"),
                    whitelist_characters="_-",
                ),
            ),
            "field_type": field_type_strategy(),
            "question": st.text(min_size=1, max_size=500),
            "required": st.booleans(),
        }
    ).map(
        lambda d: CustomField(
            id=d["id"],
            field_type=d["field_type"],
            question=d["question"],
            required=d["required"],
            options=[],
        )
    )


def poll_field_strategy() -> st.SearchStrategy[CustomField]:
    return st.fixed_dictionaries(
        {
            "id": st.text(
                min_size=1,
                max_size=50,
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd"),
                    whitelist_characters="_-",
                ),
            ),
            "question": st.text(min_size=1, max_size=500),
            "required": st.booleans(),
            "options": st.lists(st.text(min_size=1, max_size=100), min_size=2, max_size=10),
        }
    ).map(
        lambda d: CustomField(
            id=d["id"],
            field_type=FieldType.POLL_SINGLE,
            question=d["question"],
            required=d["required"],
            options=d["options"],
        )
    )


def form_schema_strategy() -> st.SearchStrategy[FormSchema]:
    return (
        st.lists(
            st.one_of(custom_field_strategy(), poll_field_strategy()),
            min_size=0,
            max_size=20,
        )
        .filter(lambda fields: len({f.id for f in fields}) == len(fields))
        .map(lambda fields: FormSchema(fields=fields))
    )


@given(form_schema_strategy())
@settings(max_examples=200)
def test_form_schema_serialization_round_trip(schema: FormSchema) -> None:
    """Property 1: Serializing and deserializing a FormSchema preserves all data."""
    serialized = json.dumps(
        [
            {
                "id": f.id,
                "field_type": f.field_type.value,
                "question": f.question,
                "required": f.required,
                "options": f.options,
            }
            for f in schema.fields
        ]
    )
    deserialized_data = json.loads(serialized)
    reconstructed = FormSchema(
        fields=[
            CustomField(
                id=d["id"],
                field_type=FieldType(d["field_type"]),
                question=d["question"],
                required=d["required"],
                options=d["options"],
            )
            for d in deserialized_data
        ]
    )
    assert len(reconstructed.fields) == len(schema.fields)
    for orig, recon in zip(schema.fields, reconstructed.fields, strict=True):
        assert orig.id == recon.id
        assert orig.field_type == recon.field_type
        assert orig.question == recon.question
        assert orig.required == recon.required
        assert orig.options == recon.options
