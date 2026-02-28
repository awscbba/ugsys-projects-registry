"""Response DTOs for public (unauthenticated) endpoints.

PublicRegisterResult: Result of a public user registration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PublicRegisterResult:
    """Result of a public user registration request."""

    user_id: str
    email: str
    message: str = "Registration successful"
