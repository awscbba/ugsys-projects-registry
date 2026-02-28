"""Response DTOs for project resources.

ProjectResponse: Full project data including admin-only fields.
PublicProjectResponse: Public-safe project data (no notification_emails).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.project import Project


@dataclass
class ProjectResponse:
    """Full project response including all fields (admin/owner use)."""

    id: str
    name: str
    description: str
    rich_text: str
    category: str
    status: str
    start_date: str
    end_date: str
    max_participants: int
    current_participants: int
    notification_emails: list[str]
    is_enabled: bool
    created_by: str
    created_at: str
    updated_at: str
    image: str | None = None

    @classmethod
    def from_domain(cls, project: Project) -> ProjectResponse:
        """Convert a Project domain entity to a ProjectResponse DTO."""
        image_url: str | None = None
        if project.images:
            image_url = project.images[0].cloudfront_url

        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            rich_text=project.rich_text,
            category=project.category,
            status=str(project.status),
            start_date=project.start_date,
            end_date=project.end_date,
            max_participants=project.max_participants,
            current_participants=project.current_participants,
            notification_emails=list(project.notification_emails),
            is_enabled=project.is_enabled,
            created_by=project.created_by,
            created_at=project.created_at,
            updated_at=project.updated_at,
            image=image_url,
        )


@dataclass
class PublicProjectResponse:
    """Public-safe project response — excludes notification_emails."""

    id: str
    name: str
    description: str
    rich_text: str
    category: str
    status: str
    start_date: str
    end_date: str
    max_participants: int
    current_participants: int
    is_enabled: bool
    created_by: str
    created_at: str
    updated_at: str
    image: str | None = None

    @classmethod
    def from_domain(cls, project: Project) -> PublicProjectResponse:
        """Convert a Project domain entity to a PublicProjectResponse DTO."""
        image_url: str | None = None
        if project.images:
            image_url = project.images[0].cloudfront_url

        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            rich_text=project.rich_text,
            category=project.category,
            status=str(project.status),
            start_date=project.start_date,
            end_date=project.end_date,
            max_participants=project.max_participants,
            current_participants=project.current_participants,
            is_enabled=project.is_enabled,
            created_by=project.created_by,
            created_at=project.created_at,
            updated_at=project.updated_at,
            image=image_url,
        )
