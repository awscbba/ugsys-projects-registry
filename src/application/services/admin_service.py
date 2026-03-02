"""AdminService — admin dashboard, analytics, user management, and bulk actions.

Aggregates data from all three repositories and delegates user operations
to the IdentityClient port.
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from src.application.commands.project_commands import BulkActionCommand
from src.application.dtos.admin_dtos import (
    AnalyticsData,
    BulkActionResult,
    DashboardData,
    EnhancedDashboardData,
    ProjectStats,
    UserBulkActionResult,
)
from src.application.dtos.subscription_dtos import SubscriptionResponse
from src.application.queries.project_queries import PaginatedUsersQuery, ProjectListQuery
from src.application.tracing import traced
from src.domain.exceptions import ValidationError
from src.domain.repositories.form_submission_repository import FormSubmissionRepository
from src.domain.repositories.identity_client import IdentityClient
from src.domain.repositories.project_repository import ProjectRepository
from src.domain.repositories.subscription_repository import SubscriptionRepository
from src.domain.value_objects.project_status import ProjectStatus, SubscriptionStatus

logger = structlog.get_logger()


class AdminService:
    """Application service for admin operations."""

    def __init__(
        self,
        project_repo: ProjectRepository,
        subscription_repo: SubscriptionRepository,
        form_submission_repo: FormSubmissionRepository,
        identity_client: IdentityClient,
    ) -> None:
        self._project_repo = project_repo
        self._subscription_repo = subscription_repo
        self._form_submission_repo = form_submission_repo
        self._identity_client = identity_client

    # ── dashboard ─────────────────────────────────────────────────────────────

    @traced
    async def dashboard(self) -> DashboardData:
        """Return basic aggregate counts for the admin dashboard."""
        logger.info("admin.dashboard.started")
        start = time.perf_counter()

        projects, total_projects = await self._project_repo.list_by_query(
            ProjectListQuery(page=1, page_size=10000)
        )

        active_projects = sum(1 for p in projects if p.status == ProjectStatus.ACTIVE)

        total_subscriptions = 0
        pending_subscriptions = 0
        for project in projects:
            subs, count = await self._subscription_repo.list_by_project(
                project.id, page=1, page_size=10000
            )
            total_subscriptions += count
            pending_subscriptions += sum(1 for s in subs if s.status == SubscriptionStatus.PENDING)

        total_form_submissions = 0
        for project in projects:
            submissions = await self._form_submission_repo.list_by_project(project.id)
            total_form_submissions += len(submissions)

        result = DashboardData(
            total_projects=total_projects,
            total_subscriptions=total_subscriptions,
            total_form_submissions=total_form_submissions,
            active_projects=active_projects,
            pending_subscriptions=pending_subscriptions,
        )

        logger.info(
            "admin.dashboard.completed",
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return result

    # ── enhanced_dashboard ────────────────────────────────────────────────────

    @traced
    async def enhanced_dashboard(self) -> EnhancedDashboardData:
        """Return dashboard data enriched with per-project stats and recent signups."""
        logger.info("admin.enhanced_dashboard.started")
        start = time.perf_counter()

        projects, total_projects = await self._project_repo.list_by_query(
            ProjectListQuery(page=1, page_size=10000)
        )

        active_projects = sum(1 for p in projects if p.status == ProjectStatus.ACTIVE)

        total_subscriptions = 0
        pending_subscriptions = 0
        per_project_stats: list[ProjectStats] = []
        all_subscriptions: list[Any] = []

        for project in projects:
            subs, count = await self._subscription_repo.list_by_project(
                project.id, page=1, page_size=10000
            )
            total_subscriptions += count
            project_pending = sum(1 for s in subs if s.status == SubscriptionStatus.PENDING)
            project_active = sum(1 for s in subs if s.status == SubscriptionStatus.ACTIVE)
            pending_subscriptions += project_pending

            per_project_stats.append(
                ProjectStats(
                    project_id=project.id,
                    project_name=project.name,
                    subscription_count=count,
                    active_count=project_active,
                    pending_count=project_pending,
                )
            )
            all_subscriptions.extend(subs)

        total_form_submissions = 0
        for project in projects:
            submissions = await self._form_submission_repo.list_by_project(project.id)
            total_form_submissions += len(submissions)

        # Recent signups: sort all subscriptions by created_at desc, take first 10
        all_subscriptions.sort(key=lambda s: s.created_at, reverse=True)
        recent_signups = [SubscriptionResponse.from_domain(s) for s in all_subscriptions[:10]]

        result = EnhancedDashboardData(
            total_projects=total_projects,
            total_subscriptions=total_subscriptions,
            total_form_submissions=total_form_submissions,
            active_projects=active_projects,
            pending_subscriptions=pending_subscriptions,
            per_project_stats=per_project_stats,
            recent_signups=recent_signups,
        )

        logger.info(
            "admin.enhanced_dashboard.completed",
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return result

    # ── analytics ─────────────────────────────────────────────────────────────

    @traced
    async def analytics(self) -> AnalyticsData:
        """Return breakdown analytics by status and project."""
        logger.info("admin.analytics.started")
        start = time.perf_counter()

        projects, _ = await self._project_repo.list_by_query(
            ProjectListQuery(page=1, page_size=10000)
        )

        projects_by_status: dict[str, int] = {}
        for project in projects:
            key = str(project.status)
            projects_by_status[key] = projects_by_status.get(key, 0) + 1

        subscriptions_by_status: dict[str, int] = {}
        subscriptions_by_project: dict[str, int] = {}

        for project in projects:
            subs, count = await self._subscription_repo.list_by_project(
                project.id, page=1, page_size=10000
            )
            subscriptions_by_project[project.id] = count
            for sub in subs:
                key = str(sub.status)
                subscriptions_by_status[key] = subscriptions_by_status.get(key, 0) + 1

        result = AnalyticsData(
            subscriptions_by_status=subscriptions_by_status,
            projects_by_status=projects_by_status,
            subscriptions_by_project=subscriptions_by_project,
        )

        logger.info(
            "admin.analytics.completed",
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return result

    # ── paginated_users ───────────────────────────────────────────────────────

    @traced
    async def paginated_users(self, query: PaginatedUsersQuery) -> tuple[list[dict[str, Any]], int]:
        """Return a paginated list of users from the Identity Manager."""
        logger.info("admin.paginated_users.started", page=query.page, page_size=query.page_size)
        start = time.perf_counter()

        result = await self._identity_client.list_users(page=query.page, page_size=query.page_size)

        logger.info(
            "admin.paginated_users.completed",
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return result

    # ── bulk_action ───────────────────────────────────────────────────────────

    @traced
    async def bulk_action(self, cmd: BulkActionCommand) -> BulkActionResult:
        """Perform a bulk action (delete or deactivate) on a list of users."""
        logger.info("admin.bulk_action.started", action=cmd.action, count=len(cmd.user_ids))
        start = time.perf_counter()

        if cmd.action not in {"delete", "deactivate"}:
            raise ValidationError(
                message=f"Invalid bulk action: {cmd.action!r}",
                user_message="Action must be 'delete' or 'deactivate'",
                error_code="VALIDATION_ERROR",
            )

        if not cmd.user_ids:
            raise ValidationError(
                message="bulk_action called with empty user_ids",
                user_message="At least one user ID is required",
                error_code="VALIDATION_ERROR",
            )

        results: list[UserBulkActionResult] = []
        succeeded = 0
        failed = 0

        for user_id in cmd.user_ids:
            try:
                if cmd.action == "delete":
                    subscriptions = await self._subscription_repo.list_by_person(user_id)
                    has_blocking = any(
                        s.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PENDING)
                        for s in subscriptions
                    )
                    if has_blocking:
                        results.append(
                            UserBulkActionResult(
                                user_id=user_id,
                                success=False,
                                error_code="BUSINESS_RULE_VIOLATION",
                                message="User has active subscriptions",
                            )
                        )
                        failed += 1
                        continue

                    await self._identity_client.delete_user(user_id)
                    results.append(UserBulkActionResult(user_id=user_id, success=True))
                    succeeded += 1

                else:  # deactivate
                    await self._identity_client.deactivate_user(user_id)
                    results.append(UserBulkActionResult(user_id=user_id, success=True))
                    succeeded += 1

            except Exception as exc:
                logger.warning(
                    "admin.bulk_action.user_failed",
                    user_id=user_id,
                    action=cmd.action,
                    error=str(exc),
                )
                results.append(
                    UserBulkActionResult(
                        user_id=user_id,
                        success=False,
                        error_code="EXTERNAL_SERVICE_ERROR",
                        message=str(exc),
                    )
                )
                failed += 1

        bulk_result = BulkActionResult(
            action=cmd.action,
            total=len(cmd.user_ids),
            succeeded=succeeded,
            failed=failed,
            results=results,
        )

        logger.info(
            "admin.bulk_action.completed",
            action=cmd.action,
            succeeded=succeeded,
            failed=failed,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
        )
        return bulk_result
