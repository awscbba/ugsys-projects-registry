"""Domain entities for dynamic form schemas.

FieldType enumerates supported form field types.
CustomField represents a single field within a form schema.
FormSchema represents a collection of custom fields attached to a project.

Validation constraints (enforced in the application layer, not here):
- FormSchema: max 20 fields, unique field IDs
- CustomField.question: max 500 chars
- CustomField.options: 2-10 items for poll_single/poll_multiple types
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FieldType(StrEnum):
    """Supported form field types."""

    TEXT = "text"
    TEXTAREA = "textarea"
    POLL_SINGLE = "poll_single"
    POLL_MULTIPLE = "poll_multiple"
    DATE = "date"
    NUMBER = "number"


@dataclass
class CustomField:
    """A single field within a form schema.

    Attributes:
        id: Unique identifier within the parent schema.
        field_type: The type of input this field represents.
        question: The prompt displayed to the user (max 500 chars).
        required: Whether the field must be answered.
        options: Available choices for poll_single/poll_multiple types (2-10 items).
    """

    id: str
    field_type: FieldType
    question: str
    required: bool = False
    options: list[str] = field(default_factory=list)


@dataclass
class FormSchema:
    """A collection of custom fields attached to a project.

    Attributes:
        fields: The ordered list of custom fields (max 20).
    """

    fields: list[CustomField] = field(default_factory=list)
