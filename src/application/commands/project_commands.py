"""Command dataclasses for project write operations."""

from __future__ import annotations

from dataclasses import dataclass

from src.domain.entities.project import ProjectImage


@dataclass
class CreateProjectCommand:
    """Command to create a new project."""

    name: str
    description: str
    category: str
    start_date: str
    end_date: str
    max_participants: int
    notification_emails: list[str]
    created_by: str  # JWT sub
    rich_text: str | None = None
    image: ProjectImage | None = None


@dataclass
class UpdateProjectCommand:
    """Command to update an existing project."""

    project_id: str
    requester_id: str
    is_admin: bool
    name: str | None = None
    description: str | None = None
    rich_text: str | None = None
    category: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    max_participants: int | None = None
    notification_emails: list[str] | None = None
    image: ProjectImage | None = None
    status: str | None = None
    is_enabled: bool | None = None


@dataclass
class DeleteProjectCommand:
    """Command to delete a project."""

    project_id: str
    requester_id: str
    is_admin: bool


@dataclass
class BulkActionCommand:
    """Command to perform a bulk action on multiple users."""

    action: str
    user_ids: list[str]
    requester_id: str


@dataclass
class GenerateUploadUrlCommand:
    """Command to generate a presigned S3 upload URL."""

    file_size: int
    content_type: str
    requester_id: str
