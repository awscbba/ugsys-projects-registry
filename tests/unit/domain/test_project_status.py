"""Unit tests for ProjectStatus and SubscriptionStatus value objects."""

from enum import StrEnum

from src.domain.value_objects.project_status import ProjectStatus, SubscriptionStatus


class TestProjectStatus:
    """Tests for ProjectStatus StrEnum."""

    def test_is_str_enum(self) -> None:
        assert issubclass(ProjectStatus, StrEnum)

    def test_has_four_members(self) -> None:
        assert len(ProjectStatus) == 4

    def test_pending_value(self) -> None:
        assert ProjectStatus.PENDING == "pending"
        assert ProjectStatus.PENDING.value == "pending"

    def test_active_value(self) -> None:
        assert ProjectStatus.ACTIVE == "active"
        assert ProjectStatus.ACTIVE.value == "active"

    def test_completed_value(self) -> None:
        assert ProjectStatus.COMPLETED == "completed"
        assert ProjectStatus.COMPLETED.value == "completed"

    def test_cancelled_value(self) -> None:
        assert ProjectStatus.CANCELLED == "cancelled"
        assert ProjectStatus.CANCELLED.value == "cancelled"

    def test_string_comparison(self) -> None:
        assert ProjectStatus.PENDING == "pending"
        assert str(ProjectStatus.ACTIVE) == "active"

    def test_construction_from_string(self) -> None:
        assert ProjectStatus("pending") is ProjectStatus.PENDING
        assert ProjectStatus("active") is ProjectStatus.ACTIVE
        assert ProjectStatus("completed") is ProjectStatus.COMPLETED
        assert ProjectStatus("cancelled") is ProjectStatus.CANCELLED

    def test_invalid_value_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            ProjectStatus("invalid")


class TestSubscriptionStatus:
    """Tests for SubscriptionStatus StrEnum."""

    def test_is_str_enum(self) -> None:
        assert issubclass(SubscriptionStatus, StrEnum)

    def test_has_four_members(self) -> None:
        assert len(SubscriptionStatus) == 4

    def test_pending_value(self) -> None:
        assert SubscriptionStatus.PENDING == "pending"
        assert SubscriptionStatus.PENDING.value == "pending"

    def test_active_value(self) -> None:
        assert SubscriptionStatus.ACTIVE == "active"
        assert SubscriptionStatus.ACTIVE.value == "active"

    def test_rejected_value(self) -> None:
        assert SubscriptionStatus.REJECTED == "rejected"
        assert SubscriptionStatus.REJECTED.value == "rejected"

    def test_cancelled_value(self) -> None:
        assert SubscriptionStatus.CANCELLED == "cancelled"
        assert SubscriptionStatus.CANCELLED.value == "cancelled"

    def test_string_comparison(self) -> None:
        assert SubscriptionStatus.PENDING == "pending"
        assert str(SubscriptionStatus.ACTIVE) == "active"

    def test_construction_from_string(self) -> None:
        assert SubscriptionStatus("pending") is SubscriptionStatus.PENDING
        assert SubscriptionStatus("active") is SubscriptionStatus.ACTIVE
        assert SubscriptionStatus("rejected") is SubscriptionStatus.REJECTED
        assert SubscriptionStatus("cancelled") is SubscriptionStatus.CANCELLED

    def test_invalid_value_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            SubscriptionStatus("invalid")
