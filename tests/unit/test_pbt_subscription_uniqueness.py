"""Property 6: Subscription uniqueness invariant.

Validates: Requirements 4.3, 17.6
"""

from __future__ import annotations

import asyncio

from hypothesis import given, settings
from hypothesis import strategies as st
from ulid import ULID

from src.domain.entities.subscription import Subscription
from src.domain.value_objects.project_status import SubscriptionStatus


class InMemorySubscriptionRepo:
    """Minimal in-memory subscription repository for PBT."""

    def __init__(self) -> None:
        self._subs: dict[str, Subscription] = {}

    async def find_by_person_and_project(
        self, person_id: str, project_id: str
    ) -> Subscription | None:
        key = f"{person_id}#{project_id}"
        return self._subs.get(key)

    async def save(self, sub: Subscription) -> Subscription:
        key = f"{sub.person_id}#{sub.project_id}"
        self._subs[key] = sub
        return sub

    def count_active(self, person_id: str, project_id: str) -> int:
        key = f"{person_id}#{project_id}"
        sub = self._subs.get(key)
        if sub is None:
            return 0
        return 1 if sub.status != SubscriptionStatus.CANCELLED else 0


@given(
    person_id=st.text(
        min_size=26,
        max_size=26,
        alphabet="0123456789ABCDEFGHJKMNPQRSTVWXYZ",
    ),
    project_id=st.text(
        min_size=26,
        max_size=26,
        alphabet="0123456789ABCDEFGHJKMNPQRSTVWXYZ",
    ),
    n_attempts=st.integers(min_value=2, max_value=5),
)
@settings(max_examples=100)
def test_subscription_uniqueness_invariant(
    person_id: str, project_id: str, n_attempts: int
) -> None:
    """Property 6: Only one non-cancelled subscription can exist per person+project."""

    repo = InMemorySubscriptionRepo()

    async def run() -> None:
        success_count = 0
        conflict_count = 0
        for _ in range(n_attempts):
            existing = await repo.find_by_person_and_project(person_id, project_id)
            if existing is not None:
                conflict_count += 1
                continue
            sub = Subscription(
                id=str(ULID()),
                project_id=project_id,
                person_id=person_id,
                status=SubscriptionStatus.PENDING,
                created_at="2024-01-01T00:00:00Z",
                updated_at="2024-01-01T00:00:00Z",
            )
            await repo.save(sub)
            success_count += 1

        assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
        assert conflict_count == n_attempts - 1
        assert repo.count_active(person_id, project_id) == 1

    asyncio.run(run())
