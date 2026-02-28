"""Auth helpers — extract validated user from request state."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import Request

from src.domain.exceptions import AuthenticationError


@dataclass
class CurrentUser:
    sub: str
    email: str = ""
    roles: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return any(r in self.roles for r in ("admin", "super_admin"))

    @property
    def is_moderator(self) -> bool:
        return any(r in self.roles for r in ("moderator", "admin", "super_admin"))

    @property
    def is_super_admin(self) -> bool:
        return "super_admin" in self.roles


def get_current_user(request: Request) -> CurrentUser:
    """Extract the validated user from request state (set by AuthMiddleware)."""
    user = getattr(request.state, "user", None)
    if user is None:
        raise AuthenticationError(
            message="No authenticated user in request state",
            user_message="Authentication required",
            error_code="AUTHENTICATION_REQUIRED",
        )
    if isinstance(user, CurrentUser):
        return user
    # Handle TokenPayload from ugsys-auth-client AuthMiddleware
    if hasattr(user, "sub") and hasattr(user, "roles"):
        return CurrentUser(
            sub=user.sub,
            email=getattr(user, "email", ""),
            roles=list(user.roles),
        )
    # Handle dict-style user
    if isinstance(user, dict):
        return CurrentUser(
            sub=user.get("sub", ""),
            email=user.get("email", ""),
            roles=user.get("roles", []),
        )
    return CurrentUser(sub=str(user))
