"""Domain entity for volunteer subscriptions.

Subscription represents a volunteer's enrollment in a project.

Lifecycle: pending → active | rejected; active → cancelled.

This is a pure dataclass — validation logic belongs in the application layer.
All IDs are ULIDs (string type). All dates are ISO 8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.value_objects.project_status import SubscriptionStatus


@dataclass
class Subscription:
    """A volunteer's enrollment in a project.

    Attributes:
        id: ULID identifier.
        project_id: ULID of the associated project.
        person_id: ULID of the subscriber (from JWT sub).
        status: Current subscription lifecycle status.
        notes: Optional notes from the subscriber (max 1000 chars).
        subscription_date: ISO 8601 date when the subscription was created.
        is_active: Whether the subscription is currently active.
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last update timestamp.
        migrated_from: Source system identifier if migrated (e.g. "registry").
        migrated_at: ISO 8601 timestamp of migration.
    """

    id: str
    project_id: str
    person_id: str
    status: SubscriptionStatus = SubscriptionStatus.PENDING
    notes: str = ""
    subscription_date: str = ""
    is_active: bool = True
    created_at: str = ""
    updated_at: str = ""
    migrated_from: str | None = None
    migrated_at: str | None = None
