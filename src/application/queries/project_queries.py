"""Query dataclasses for project read operations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PaginatedUsersQuery:
    """Query for paginated user listing."""

    page: int = 1
    page_size: int = 20


@dataclass(frozen=True)
class ProjectListQuery:
    """Encapsulates all filter/sort/pagination criteria for project listing."""

    page: int = 1
    page_size: int = 20
    status: str | None = None
    category: str | None = None
    owner_id: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    search_term: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"
    tags: list[str] = field(default_factory=list)

    def has_filters(self) -> bool:
        """Return True if any filter field is set."""
        return any(
            [
                self.status,
                self.category,
                self.owner_id,
                self.date_from,
                self.date_to,
                self.search_term,
                self.tags,
            ]
        )
