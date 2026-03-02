"""Abstract repository interface for Project aggregate root.

Defines the outbound port for project persistence operations.
Infrastructure layer provides the concrete DynamoDB implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entities.project import Project
from src.domain.queries.project_queries import ProjectListQuery


class ProjectRepository(ABC):
    """Port interface for project persistence operations."""

    @abstractmethod
    async def save(self, project: Project) -> Project: ...

    @abstractmethod
    async def find_by_id(self, project_id: str) -> Project | None: ...

    @abstractmethod
    async def update(self, project: Project) -> Project: ...

    @abstractmethod
    async def delete(self, project_id: str) -> None: ...

    @abstractmethod
    async def list_paginated(
        self,
        page: int,
        page_size: int,
        status_filter: str | None = None,
        category_filter: str | None = None,
    ) -> tuple[list[Project], int]: ...

    @abstractmethod
    async def list_public(self, limit: int) -> list[Project]: ...

    @abstractmethod
    async def list_by_query(self, query: ProjectListQuery) -> tuple[list[Project], int]:
        """List projects matching the query criteria with total count."""
        ...
