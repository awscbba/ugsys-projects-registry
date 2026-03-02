"""Unit tests for Subscription domain entity.

Validates: Requirements 4.1, 4.4, 4.5, 4.6, 17.1

Tests cover:
- Creation with required fields only — verify defaults
- Creation with all fields populated
- Status can be set to all SubscriptionStatus values
- is_active flag defaults to True
- Fields are mutable (status transitions work by setting status field)
- Equality and inequality
- Migration fields default to None
"""

from src.domain.entities.subscription import Subscription
from src.domain.value_objects.project_status import SubscriptionStatus


class TestSubscriptionCreationDefaults:
    """Tests for Subscription creation with required fields only — verify defaults."""

    def _make_minimal(self) -> Subscription:
        return Subscription(id="01JSUB", project_id="01JPROJ", person_id="01JPERSON")

    def test_status_defaults_to_pending(self) -> None:
        sub = self._make_minimal()
        assert sub.status == SubscriptionStatus.PENDING

    def test_is_active_defaults_to_true(self) -> None:
        sub = self._make_minimal()
        assert sub.is_active is True

    def test_notes_defaults_to_empty(self) -> None:
        sub = self._make_minimal()
        assert sub.notes == ""

    def test_subscription_date_defaults_to_empty(self) -> None:
        sub = self._make_minimal()
        assert sub.subscription_date == ""

    def test_created_at_defaults_to_empty(self) -> None:
        sub = self._make_minimal()
        assert sub.created_at == ""

    def test_updated_at_defaults_to_empty(self) -> None:
        sub = self._make_minimal()
        assert sub.updated_at == ""

    def test_migrated_from_defaults_to_none(self) -> None:
        sub = self._make_minimal()
        assert sub.migrated_from is None

    def test_migrated_at_defaults_to_none(self) -> None:
        sub = self._make_minimal()
        assert sub.migrated_at is None

    def test_required_fields_are_set(self) -> None:
        sub = self._make_minimal()
        assert sub.id == "01JSUB"
        assert sub.project_id == "01JPROJ"
        assert sub.person_id == "01JPERSON"


class TestSubscriptionCreationAllFields:
    """Tests for Subscription creation with all fields populated."""

    def test_creation_with_all_fields(self) -> None:
        sub = Subscription(
            id="01JSUB",
            project_id="01JPROJ",
            person_id="01JPERSON",
            status=SubscriptionStatus.ACTIVE,
            notes="Interested in volunteering",
            subscription_date="2025-03-01T10:00:00Z",
            is_active=True,
            created_at="2025-03-01T10:00:00Z",
            updated_at="2025-03-02T12:00:00Z",
            migrated_from="registry",
            migrated_at="2025-01-10T08:00:00Z",
        )
        assert sub.id == "01JSUB"
        assert sub.project_id == "01JPROJ"
        assert sub.person_id == "01JPERSON"
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.notes == "Interested in volunteering"
        assert sub.subscription_date == "2025-03-01T10:00:00Z"
        assert sub.is_active is True
        assert sub.created_at == "2025-03-01T10:00:00Z"
        assert sub.updated_at == "2025-03-02T12:00:00Z"
        assert sub.migrated_from == "registry"
        assert sub.migrated_at == "2025-01-10T08:00:00Z"


class TestSubscriptionStatusValues:
    """Tests for setting status to all SubscriptionStatus values."""

    def test_status_pending(self) -> None:
        sub = Subscription(
            id="01JS",
            project_id="01JP",
            person_id="01JPER",
            status=SubscriptionStatus.PENDING,
        )
        assert sub.status == SubscriptionStatus.PENDING
        assert sub.status.value == "pending"

    def test_status_active(self) -> None:
        sub = Subscription(
            id="01JS",
            project_id="01JP",
            person_id="01JPER",
            status=SubscriptionStatus.ACTIVE,
        )
        assert sub.status == SubscriptionStatus.ACTIVE
        assert sub.status.value == "active"

    def test_status_rejected(self) -> None:
        sub = Subscription(
            id="01JS",
            project_id="01JP",
            person_id="01JPER",
            status=SubscriptionStatus.REJECTED,
        )
        assert sub.status == SubscriptionStatus.REJECTED
        assert sub.status.value == "rejected"

    def test_status_cancelled(self) -> None:
        sub = Subscription(
            id="01JS",
            project_id="01JP",
            person_id="01JPER",
            status=SubscriptionStatus.CANCELLED,
        )
        assert sub.status == SubscriptionStatus.CANCELLED
        assert sub.status.value == "cancelled"


class TestSubscriptionMutability:
    """Tests for Subscription fields being mutable — status transitions work by setting status."""

    def test_status_transition_pending_to_active(self) -> None:
        sub = Subscription(id="01JS", project_id="01JP", person_id="01JPER")
        assert sub.status == SubscriptionStatus.PENDING
        sub.status = SubscriptionStatus.ACTIVE
        assert sub.status == SubscriptionStatus.ACTIVE

    def test_status_transition_pending_to_rejected(self) -> None:
        sub = Subscription(id="01JS", project_id="01JP", person_id="01JPER")
        sub.status = SubscriptionStatus.REJECTED
        assert sub.status == SubscriptionStatus.REJECTED

    def test_status_transition_active_to_cancelled(self) -> None:
        sub = Subscription(
            id="01JS",
            project_id="01JP",
            person_id="01JPER",
            status=SubscriptionStatus.ACTIVE,
        )
        sub.status = SubscriptionStatus.CANCELLED
        assert sub.status == SubscriptionStatus.CANCELLED

    def test_status_transition_pending_to_cancelled(self) -> None:
        sub = Subscription(id="01JS", project_id="01JP", person_id="01JPER")
        sub.status = SubscriptionStatus.CANCELLED
        assert sub.status == SubscriptionStatus.CANCELLED

    def test_is_active_is_mutable(self) -> None:
        sub = Subscription(id="01JS", project_id="01JP", person_id="01JPER")
        assert sub.is_active is True
        sub.is_active = False
        assert sub.is_active is False

    def test_notes_is_mutable(self) -> None:
        sub = Subscription(id="01JS", project_id="01JP", person_id="01JPER")
        sub.notes = "Updated notes"
        assert sub.notes == "Updated notes"

    def test_updated_at_is_mutable(self) -> None:
        sub = Subscription(id="01JS", project_id="01JP", person_id="01JPER")
        sub.updated_at = "2025-06-01T00:00:00Z"
        assert sub.updated_at == "2025-06-01T00:00:00Z"


class TestSubscriptionEquality:
    """Tests for Subscription equality and inequality."""

    def test_equality_with_same_values(self) -> None:
        a = Subscription(id="01JS", project_id="01JP", person_id="01JPER")
        b = Subscription(id="01JS", project_id="01JP", person_id="01JPER")
        assert a == b

    def test_inequality_with_different_id(self) -> None:
        a = Subscription(id="01JS1", project_id="01JP", person_id="01JPER")
        b = Subscription(id="01JS2", project_id="01JP", person_id="01JPER")
        assert a != b

    def test_inequality_with_different_project_id(self) -> None:
        a = Subscription(id="01JS", project_id="01JP1", person_id="01JPER")
        b = Subscription(id="01JS", project_id="01JP2", person_id="01JPER")
        assert a != b

    def test_inequality_with_different_person_id(self) -> None:
        a = Subscription(id="01JS", project_id="01JP", person_id="01JPER1")
        b = Subscription(id="01JS", project_id="01JP", person_id="01JPER2")
        assert a != b

    def test_inequality_with_different_status(self) -> None:
        a = Subscription(
            id="01JS",
            project_id="01JP",
            person_id="01JPER",
            status=SubscriptionStatus.PENDING,
        )
        b = Subscription(
            id="01JS",
            project_id="01JP",
            person_id="01JPER",
            status=SubscriptionStatus.ACTIVE,
        )
        assert a != b

    def test_inequality_with_different_is_active(self) -> None:
        a = Subscription(id="01JS", project_id="01JP", person_id="01JPER", is_active=True)
        b = Subscription(id="01JS", project_id="01JP", person_id="01JPER", is_active=False)
        assert a != b
