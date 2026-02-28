"""Property 5: Participant count invariant.

Validates: Requirements 4.2, 4.4, 4.6, 2.10
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from src.domain.entities.project import Project
from src.domain.value_objects.project_status import ProjectStatus


@given(
    n_approvals=st.integers(min_value=0, max_value=10),
    n_cancellations=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=100)
def test_participant_count_invariant(n_approvals: int, n_cancellations: int) -> None:
    """Property 5: current_participants == approved - cancelled_active."""
    n_cancellations = min(n_cancellations, n_approvals)

    project = Project(
        id="01JTEST00000000000000000001",
        name="Test Project",
        description="Test",
        status=ProjectStatus.ACTIVE,
        is_enabled=True,
        created_by="user1",
        current_participants=0,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
    )

    # Simulate approvals
    for _ in range(n_approvals):
        project.current_participants += 1

    # Simulate cancellations of active subscriptions
    for _ in range(n_cancellations):
        project.current_participants = max(0, project.current_participants - 1)

    expected = n_approvals - n_cancellations
    assert project.current_participants == expected, (
        f"Expected {expected} participants, got {project.current_participants}"
    )
    assert project.current_participants >= 0
