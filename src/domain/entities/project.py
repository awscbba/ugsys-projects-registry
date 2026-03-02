"""Domain entities for the project catalog.

ProjectImage represents an image asset associated with a project.
Project represents a community initiative with a defined lifecycle.

These are pure dataclasses — validation logic belongs in the application layer.
All IDs are ULIDs (string type). All dates are ISO 8601 strings.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.entities.form_schema import FormSchema
from src.domain.value_objects.project_status import ProjectStatus


@dataclass
class ProjectImage:
    """An image asset associated with a project, stored in S3 and served via CloudFront.

    Attributes:
        image_id: ULID identifier for the image.
        filename: Original filename of the uploaded image.
        content_type: MIME type (e.g. image/jpeg, image/png).
        cloudfront_url: Public CDN URL for the image.
        uploaded_at: ISO 8601 timestamp of when the image was uploaded.
    """

    image_id: str
    filename: str
    content_type: str
    cloudfront_url: str
    uploaded_at: str


@dataclass
class Project:
    """A community initiative with a defined lifecycle.

    Lifecycle: pending → active → completed | cancelled.

    Attributes:
        id: ULID identifier.
        name: Project title (max 200 chars).
        description: Short description (max 5000 chars).
        rich_text: Extended content (max 10000 chars).
        category: Project category label.
        status: Current lifecycle status.
        is_enabled: Whether the project is visible to the public.
        max_participants: Maximum allowed volunteers (>= 1).
        current_participants: Current count of active subscriptions.
        start_date: ISO 8601 project start date.
        end_date: ISO 8601 project end date (must be >= start_date).
        created_by: ULID of the person who created the project.
        notification_emails: Emails notified on new subscriptions.
        enable_subscription_notifications: Whether to send subscription notifications.
        images: List of project images.
        form_schema: Optional dynamic form attached to the project.
        created_at: ISO 8601 creation timestamp.
        updated_at: ISO 8601 last update timestamp.
        migrated_from: Source system identifier if migrated (e.g. "registry").
        migrated_at: ISO 8601 timestamp of migration.
    """

    # Identity
    id: str
    name: str
    description: str
    rich_text: str = ""
    category: str = ""
    # Lifecycle
    status: ProjectStatus = ProjectStatus.PENDING
    is_enabled: bool = False
    # Participants
    max_participants: int = 0
    current_participants: int = 0
    # Dates
    start_date: str = ""
    end_date: str = ""
    # Ownership
    created_by: str = ""
    # Notifications
    notification_emails: list[str] = field(default_factory=list)
    enable_subscription_notifications: bool = False
    # Images
    images: list[ProjectImage] = field(default_factory=list)
    # Form
    form_schema: FormSchema | None = None
    # Timestamps
    created_at: str = ""
    updated_at: str = ""
    # Migration
    migrated_from: str | None = None
    migrated_at: str | None = None
