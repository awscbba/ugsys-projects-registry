"""Abstract interface for Identity Manager integration.

Defines the outbound port for communicating with ugsys-identity-manager.
Infrastructure layer provides the concrete HTTP client implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class IdentityClient(ABC):
    """Port interface for Identity Manager service calls."""

    @abstractmethod
    async def check_email_exists(self, email: str) -> bool: ...

    @abstractmethod
    async def create_user(self, email: str, full_name: str, password: str) -> str:
        """Create a user in Identity Manager.

        Returns the new user_id.
        """
        ...

    @abstractmethod
    async def register_service(
        self,
        service_id: str,
        display_name: str,
        version: str,
        nav_icon: str,
        health_url: str,
        config_schema: dict[str, Any],
        roles: list[dict[str, str]],
    ) -> None: ...

    @abstractmethod
    async def get_service_config(self, service_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def list_users(self, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
        """List users with pagination. Returns (users, total)."""
        ...

    @abstractmethod
    async def delete_user(self, user_id: str) -> None: ...

    @abstractmethod
    async def deactivate_user(self, user_id: str) -> None: ...
