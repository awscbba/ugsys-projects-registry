"""Query dataclasses for project read operations."""

from __future__ import annotations

from dataclasses import dataclass

# Re-export from domain layer — application code can import from either location
from src.domain.queries.project_queries import ProjectListQuery as ProjectListQuery


@dataclass(frozen=True)
class PaginatedUsersQuery:
    """Query for paginated user listing."""

    page: int = 1
    page_size: int = 20
