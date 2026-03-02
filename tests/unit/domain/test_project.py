"""Unit tests for Project and ProjectImage domain entities.

Validates: Requirements 2.1, 2.2, 2.3, 17.1

Tests cover:
- Project creation with required fields only — verify defaults
- Project creation with all fields populated
- ProjectImage creation and equality
- Project with images, form_schema, notification_emails, migration fields
- Project default for max_participants=0
- Project mutability, equality, inequality
- List fields independence per instance
"""

from src.domain.entities.form_schema import CustomField, FieldType, FormSchema
from src.domain.entities.project import Project, ProjectImage
from src.domain.value_objects.project_status import ProjectStatus


class TestProjectImage:
    """Tests for ProjectImage dataclass."""

    def test_creation_with_all_fields(self) -> None:
        img = ProjectImage(
            image_id="01JXYZ",
            filename="banner.jpg",
            content_type="image/jpeg",
            cloudfront_url="https://cdn.cbba.cloud.org.bo/banner.jpg",
            uploaded_at="2025-01-15T10:00:00Z",
        )
        assert img.image_id == "01JXYZ"
        assert img.filename == "banner.jpg"
        assert img.content_type == "image/jpeg"
        assert img.cloudfront_url == "https://cdn.cbba.cloud.org.bo/banner.jpg"
        assert img.uploaded_at == "2025-01-15T10:00:00Z"

    def test_equality_same_values(self) -> None:
        a = ProjectImage(
            image_id="01JXYZ",
            filename="banner.jpg",
            content_type="image/jpeg",
            cloudfront_url="https://cdn.cbba.cloud.org.bo/banner.jpg",
            uploaded_at="2025-01-15T10:00:00Z",
        )
        b = ProjectImage(
            image_id="01JXYZ",
            filename="banner.jpg",
            content_type="image/jpeg",
            cloudfront_url="https://cdn.cbba.cloud.org.bo/banner.jpg",
            uploaded_at="2025-01-15T10:00:00Z",
        )
        assert a == b

    def test_inequality_different_values(self) -> None:
        a = ProjectImage(
            image_id="01JXYZ",
            filename="banner.jpg",
            content_type="image/jpeg",
            cloudfront_url="https://cdn.cbba.cloud.org.bo/banner.jpg",
            uploaded_at="2025-01-15T10:00:00Z",
        )
        b = ProjectImage(
            image_id="01JABC",
            filename="logo.png",
            content_type="image/png",
            cloudfront_url="https://cdn.cbba.cloud.org.bo/logo.png",
            uploaded_at="2025-01-16T10:00:00Z",
        )
        assert a != b


class TestProjectCreationDefaults:
    """Tests for Project creation with required fields only — verify defaults."""

    def _make_minimal_project(self) -> Project:
        return Project(id="01JXYZ", name="Test Project", description="A test project")

    def test_status_defaults_to_pending(self) -> None:
        project = self._make_minimal_project()
        assert project.status == ProjectStatus.PENDING

    def test_current_participants_defaults_to_zero(self) -> None:
        project = self._make_minimal_project()
        assert project.current_participants == 0

    def test_is_enabled_defaults_to_false(self) -> None:
        project = self._make_minimal_project()
        assert project.is_enabled is False

    def test_rich_text_defaults_to_empty(self) -> None:
        project = self._make_minimal_project()
        assert project.rich_text == ""

    def test_category_defaults_to_empty(self) -> None:
        project = self._make_minimal_project()
        assert project.category == ""

    def test_max_participants_defaults_to_zero(self) -> None:
        project = self._make_minimal_project()
        assert project.max_participants == 0

    def test_start_date_defaults_to_empty(self) -> None:
        project = self._make_minimal_project()
        assert project.start_date == ""

    def test_end_date_defaults_to_empty(self) -> None:
        project = self._make_minimal_project()
        assert project.end_date == ""

    def test_created_by_defaults_to_empty(self) -> None:
        project = self._make_minimal_project()
        assert project.created_by == ""

    def test_notification_emails_defaults_to_empty_list(self) -> None:
        project = self._make_minimal_project()
        assert project.notification_emails == []

    def test_enable_subscription_notifications_defaults_to_false(self) -> None:
        project = self._make_minimal_project()
        assert project.enable_subscription_notifications is False

    def test_images_defaults_to_empty_list(self) -> None:
        project = self._make_minimal_project()
        assert project.images == []

    def test_form_schema_defaults_to_none(self) -> None:
        project = self._make_minimal_project()
        assert project.form_schema is None

    def test_created_at_defaults_to_empty(self) -> None:
        project = self._make_minimal_project()
        assert project.created_at == ""

    def test_updated_at_defaults_to_empty(self) -> None:
        project = self._make_minimal_project()
        assert project.updated_at == ""

    def test_migrated_from_defaults_to_none(self) -> None:
        project = self._make_minimal_project()
        assert project.migrated_from is None

    def test_migrated_at_defaults_to_none(self) -> None:
        project = self._make_minimal_project()
        assert project.migrated_at is None

    def test_required_fields_are_set(self) -> None:
        project = self._make_minimal_project()
        assert project.id == "01JXYZ"
        assert project.name == "Test Project"
        assert project.description == "A test project"


class TestProjectCreationAllFields:
    """Tests for Project creation with all fields populated."""

    def test_creation_with_all_fields(self) -> None:
        img = ProjectImage(
            image_id="01JIMG",
            filename="photo.png",
            content_type="image/png",
            cloudfront_url="https://cdn.cbba.cloud.org.bo/photo.png",
            uploaded_at="2025-01-15T10:00:00Z",
        )
        schema = FormSchema(
            fields=[CustomField(id="f1", field_type=FieldType.TEXT, question="Name?")]
        )
        project = Project(
            id="01JABC",
            name="Full Project",
            description="All fields set",
            rich_text="<p>Rich content</p>",
            category="community",
            status=ProjectStatus.ACTIVE,
            is_enabled=True,
            max_participants=50,
            current_participants=10,
            start_date="2025-03-01T00:00:00Z",
            end_date="2025-06-30T23:59:59Z",
            created_by="01JOWNER",
            notification_emails=["admin@example.com", "mod@example.com"],
            enable_subscription_notifications=True,
            images=[img],
            form_schema=schema,
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-15T12:00:00Z",
            migrated_from="registry",
            migrated_at="2025-01-10T08:00:00Z",
        )
        assert project.id == "01JABC"
        assert project.name == "Full Project"
        assert project.description == "All fields set"
        assert project.rich_text == "<p>Rich content</p>"
        assert project.category == "community"
        assert project.status == ProjectStatus.ACTIVE
        assert project.is_enabled is True
        assert project.max_participants == 50
        assert project.current_participants == 10
        assert project.start_date == "2025-03-01T00:00:00Z"
        assert project.end_date == "2025-06-30T23:59:59Z"
        assert project.created_by == "01JOWNER"
        assert project.notification_emails == ["admin@example.com", "mod@example.com"]
        assert project.enable_subscription_notifications is True
        assert len(project.images) == 1
        assert project.images[0].image_id == "01JIMG"
        assert project.form_schema is not None
        assert len(project.form_schema.fields) == 1
        assert project.created_at == "2025-01-01T00:00:00Z"
        assert project.updated_at == "2025-01-15T12:00:00Z"
        assert project.migrated_from == "registry"
        assert project.migrated_at == "2025-01-10T08:00:00Z"


class TestProjectWithImages:
    """Tests for Project with images list."""

    def test_project_with_multiple_images(self) -> None:
        images = [
            ProjectImage(
                image_id=f"01JIMG{i}",
                filename=f"img{i}.jpg",
                content_type="image/jpeg",
                cloudfront_url=f"https://cdn.cbba.cloud.org.bo/img{i}.jpg",
                uploaded_at="2025-01-15T10:00:00Z",
            )
            for i in range(3)
        ]
        project = Project(id="01JP", name="P", description="D", images=images)
        assert len(project.images) == 3
        assert project.images[0].image_id == "01JIMG0"
        assert project.images[2].filename == "img2.jpg"


class TestProjectWithFormSchema:
    """Tests for Project with form_schema."""

    def test_project_with_form_schema(self) -> None:
        schema = FormSchema(
            fields=[
                CustomField(id="f1", field_type=FieldType.TEXT, question="Name?"),
                CustomField(
                    id="f2",
                    field_type=FieldType.POLL_SINGLE,
                    question="Preference?",
                    options=["A", "B"],
                ),
            ]
        )
        project = Project(id="01JP", name="P", description="D", form_schema=schema)
        assert project.form_schema is not None
        assert len(project.form_schema.fields) == 2
        assert project.form_schema.fields[1].options == ["A", "B"]


class TestProjectWithNotificationEmails:
    """Tests for Project with notification_emails."""

    def test_project_with_notification_emails(self) -> None:
        emails = ["admin@example.com", "mod@example.com"]
        project = Project(
            id="01JP",
            name="P",
            description="D",
            notification_emails=emails,
            enable_subscription_notifications=True,
        )
        assert project.notification_emails == ["admin@example.com", "mod@example.com"]
        assert project.enable_subscription_notifications is True


class TestProjectWithMigrationFields:
    """Tests for Project with migration fields."""

    def test_project_with_migration_fields(self) -> None:
        project = Project(
            id="01JP",
            name="P",
            description="D",
            migrated_from="registry",
            migrated_at="2025-01-10T08:00:00Z",
        )
        assert project.migrated_from == "registry"
        assert project.migrated_at == "2025-01-10T08:00:00Z"


class TestProjectMutability:
    """Tests for Project fields being mutable (not frozen)."""

    def test_name_is_mutable(self) -> None:
        project = Project(id="01JP", name="Original", description="D")
        project.name = "Updated"
        assert project.name == "Updated"

    def test_status_is_mutable(self) -> None:
        project = Project(id="01JP", name="P", description="D")
        assert project.status == ProjectStatus.PENDING
        project.status = ProjectStatus.ACTIVE
        assert project.status == ProjectStatus.ACTIVE

    def test_current_participants_is_mutable(self) -> None:
        project = Project(id="01JP", name="P", description="D")
        project.current_participants = 5
        assert project.current_participants == 5

    def test_is_enabled_is_mutable(self) -> None:
        project = Project(id="01JP", name="P", description="D")
        project.is_enabled = True
        assert project.is_enabled is True

    def test_images_list_is_mutable(self) -> None:
        project = Project(id="01JP", name="P", description="D")
        img = ProjectImage(
            image_id="01JIMG",
            filename="new.jpg",
            content_type="image/jpeg",
            cloudfront_url="https://cdn.cbba.cloud.org.bo/new.jpg",
            uploaded_at="2025-01-15T10:00:00Z",
        )
        project.images.append(img)
        assert len(project.images) == 1


class TestProjectEquality:
    """Tests for Project equality and inequality."""

    def test_equality_with_same_values(self) -> None:
        a = Project(id="01JP", name="P", description="D")
        b = Project(id="01JP", name="P", description="D")
        assert a == b

    def test_inequality_with_different_id(self) -> None:
        a = Project(id="01JP1", name="P", description="D")
        b = Project(id="01JP2", name="P", description="D")
        assert a != b

    def test_inequality_with_different_name(self) -> None:
        a = Project(id="01JP", name="Alpha", description="D")
        b = Project(id="01JP", name="Beta", description="D")
        assert a != b

    def test_inequality_with_different_status(self) -> None:
        a = Project(id="01JP", name="P", description="D", status=ProjectStatus.PENDING)
        b = Project(id="01JP", name="P", description="D", status=ProjectStatus.ACTIVE)
        assert a != b


class TestProjectListFieldsIndependence:
    """Tests for list fields being independent per instance."""

    def test_notification_emails_independent(self) -> None:
        a = Project(id="01JPA", name="A", description="D")
        b = Project(id="01JPB", name="B", description="D")
        a.notification_emails.append("admin@example.com")
        assert len(b.notification_emails) == 0

    def test_images_independent(self) -> None:
        a = Project(id="01JPA", name="A", description="D")
        b = Project(id="01JPB", name="B", description="D")
        a.images.append(
            ProjectImage(
                image_id="01JIMG",
                filename="x.jpg",
                content_type="image/jpeg",
                cloudfront_url="https://cdn.cbba.cloud.org.bo/x.jpg",
                uploaded_at="2025-01-15T10:00:00Z",
            )
        )
        assert len(b.images) == 0
