"""Response DTOs for subscription resources.

SubscriptionResponse: Full subscription data.
EnrichedSubscriptionResponse: Subscription with optional project context.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.subscription import Subscription


@dataclass
class SubscriptionResponse:
    """Full subscription response."""

    id: str
    project_id: str
    person_id: str
    status: str
    notes: str
    subscription_date: str
    is_active: bool
    created_at: str
    updated_at: str
    migrated_from: str | None = None
    migrated_at: str | None = None

    @classmethod
    def from_domain(cls, sub: Subscription) -> SubscriptionResponse:
        """Convert a Subscription domain entity to a SubscriptionResponse DTO."""
        return cls(
            id=sub.id,
            project_id=sub.project_id,
            person_id=sub.person_id,
            status=str(sub.status),
            notes=sub.notes,
            subscription_date=sub.subscription_date,
            is_active=sub.is_active,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            migrated_from=sub.migrated_from,
            migrated_at=sub.migrated_at,
        )


@dataclass
class EnrichedSubscriptionResponse:
    """Subscription response enriched with project context."""

    id: str
    project_id: str
    person_id: str
    status: str
    notes: str
    subscription_date: str
    is_active: bool
    created_at: str
    updated_at: str
    migrated_from: str | None = None
    migrated_at: str | None = None
    project_name: str | None = None
    project_status: str | None = None

    @classmethod
    def from_domain(
        cls,
        sub: Subscription,
        project_name: str | None = None,
        project_status: str | None = None,
    ) -> EnrichedSubscriptionResponse:
        """Convert a Subscription domain entity to an EnrichedSubscriptionResponse DTO."""
        return cls(
            id=sub.id,
            project_id=sub.project_id,
            person_id=sub.person_id,
            status=str(sub.status),
            notes=sub.notes,
            subscription_date=sub.subscription_date,
            is_active=sub.is_active,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            migrated_from=sub.migrated_from,
            migrated_at=sub.migrated_at,
            project_name=project_name,
            project_status=project_status,
        )
