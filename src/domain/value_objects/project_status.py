"""Value objects for project and subscription status lifecycles."""

from enum import StrEnum


class ProjectStatus(StrEnum):
    """Project lifecycle status: pending → active → completed | cancelled."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SubscriptionStatus(StrEnum):
    """Subscription lifecycle status: pending → active | rejected; active → cancelled."""

    PENDING = "pending"
    ACTIVE = "active"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
