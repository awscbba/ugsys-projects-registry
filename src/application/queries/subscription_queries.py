"""Query dataclasses for subscription read operations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaginatedUsersQuery:
    """Encapsulates pagination and search criteria for user listing."""

    page: int = 1
    page_size: int = 20
    search_term: str | None = None
