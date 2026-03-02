"""Response DTOs for admin dashboard and bulk operations.

DashboardData: Basic aggregate counts.
ProjectStats: Per-project subscription statistics.
EnhancedDashboardData: Dashboard with per-project stats and recent signups.
AnalyticsData: Breakdown analytics by status and project.
UserBulkActionResult: Per-user result of a bulk action.
BulkActionResult: Aggregate result of a bulk action operation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.application.dtos.subscription_dtos import SubscriptionResponse


@dataclass
class DashboardData:
    """Basic aggregate counts for the admin dashboard."""

    total_projects: int
    total_subscriptions: int
    total_form_submissions: int
    active_projects: int
    pending_subscriptions: int


@dataclass
class ProjectStats:
    """Per-project subscription statistics."""

    project_id: str
    project_name: str
    subscription_count: int
    active_count: int
    pending_count: int


@dataclass
class EnhancedDashboardData:
    """Dashboard data enriched with per-project stats and recent signups."""

    total_projects: int
    total_subscriptions: int
    total_form_submissions: int
    active_projects: int
    pending_subscriptions: int
    per_project_stats: list[ProjectStats] = field(default_factory=list)
    recent_signups: list[SubscriptionResponse] = field(default_factory=list)


@dataclass
class AnalyticsData:
    """Breakdown analytics by status and project."""

    subscriptions_by_status: dict[str, int]
    projects_by_status: dict[str, int]
    subscriptions_by_project: dict[str, int]


@dataclass
class UserBulkActionResult:
    """Per-user result of a bulk action."""

    user_id: str
    success: bool
    error_code: str | None = None
    message: str | None = None


@dataclass
class BulkActionResult:
    """Aggregate result of a bulk action operation."""

    action: str
    total: int
    succeeded: int
    failed: int
    results: list[UserBulkActionResult] = field(default_factory=list)
