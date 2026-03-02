"""Command dataclasses for subscription write operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CreateSubscriptionCommand:
    """Command to create a new subscription."""

    project_id: str
    person_id: str
    notes: str | None = None
    is_super_admin: bool = False


@dataclass
class ApproveSubscriptionCommand:
    """Command to approve a pending subscription."""

    subscription_id: str
    project_id: str
    admin_id: str


@dataclass
class RejectSubscriptionCommand:
    """Command to reject a pending subscription."""

    subscription_id: str
    project_id: str
    admin_id: str
    reason: str | None = None


@dataclass
class CancelSubscriptionCommand:
    """Command to cancel an existing subscription."""

    subscription_id: str
    project_id: str
    requester_id: str
    is_admin: bool = False
