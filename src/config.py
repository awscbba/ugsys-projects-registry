"""Service configuration — pydantic-settings backed by env vars / .env file."""

from __future__ import annotations

from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Service registration schema (Section 14.2 of platform-contract)
# ---------------------------------------------------------------------------

SERVICE_CONFIG_SCHEMA: dict[str, Any] = {
    "max_subscriptions_per_project": {
        "type": "integer",
        "default": 100,
        "description": "Maximum number of subscriptions allowed per project",
    },
    "admin_notification_email": {
        "type": "string",
        "default": "",
        "description": "Email address for admin notifications",
    },
    "subscription_approval_required": {
        "type": "boolean",
        "default": True,
        "description": "Whether subscriptions require admin approval before becoming active",
    },
}

SERVICE_ROLES: list[dict[str, str]] = [
    {
        "role": "admin",
        "description": "Full access to all project and subscription management",
    },
    {
        "role": "moderator",
        "description": "Can view subscriptions and manage project content",
    },
    {
        "role": "super_admin",
        "description": "Platform super-admin — subscriptions auto-approved",
    },
]


class Settings(BaseSettings):
    # ── Service identity ────────────────────────────────────────────────────
    service_name: str = "ugsys-projects-registry"
    service_id: str = "ugsys-projects-registry"
    display_name: str = "Projects Registry"
    version: str = "0.1.0"
    nav_icon: str = "folder"
    environment: str = "dev"
    aws_region: str = "us-east-1"
    log_level: str = "INFO"

    # ── DynamoDB ────────────────────────────────────────────────────────────
    dynamodb_table_prefix: str = "ugsys"
    projects_table_name: str = "ugsys-projects-dev"
    subscriptions_table_name: str = "ugsys-subscriptions-dev"
    form_submissions_table_name: str = "ugsys-form-submissions-dev"

    # ── S3 / CloudFront ─────────────────────────────────────────────────────
    images_bucket_name: str = "ugsys-project-images-dev"
    cloudfront_domain: str = ""

    # ── EventBridge ─────────────────────────────────────────────────────────
    event_bus_name: str = "ugsys-event-bus"

    # ── Identity Manager ────────────────────────────────────────────────────
    identity_manager_url: str = "http://localhost:8001"
    identity_manager_client_id: str = ""
    identity_manager_client_secret: str = ""

    # ── Cognito JWT validation ───────────────────────────────────────────────
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_region: str = "us-east-1"

    @property
    def cognito_jwks_url(self) -> str:
        """Cognito JWKS endpoint for RS256 public key fetching."""
        if self.cognito_user_pool_id and self.cognito_region:
            return (
                f"https://cognito-idp.{self.cognito_region}.amazonaws.com/"
                f"{self.cognito_user_pool_id}/.well-known/jwks.json"
            )
        return ""

    # ── Public URL ──────────────────────────────────────────────────────────
    public_base_url: str = "https://api.cbba.cloud.org.bo/projects"

    # ── CORS ────────────────────────────────────────────────────────────────
    # All browser-facing origins that may call this API.
    # Override via ALLOWED_ORIGINS env var (comma-separated) in prod.
    allowed_origins: list[str] = [
        "https://registry.apps.cloud.org.bo",  # projects registry SPA
        "https://admin.apps.cloud.org.bo",  # admin panel
        "https://auth.apps.cloud.org.bo",  # identity manager SPA (if any)
        "https://messaging.apps.cloud.org.bo",  # omnichannel frontend (future)
    ]

    # ── Operator-configurable (overridable via remote config) ───────────────
    max_subscriptions_per_project: int = 100
    admin_notification_email: str = ""
    subscription_approval_required: bool = True

    # ── X-Ray tracing ────────────────────────────────────────────────────────
    xray_tracing_enabled: bool = False
    xray_sampling_rate: float = 0.05

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    def apply_remote_config(self, config: dict[str, Any]) -> None:
        """Apply operator-configurable fields from remote config (non-fatal)."""
        if "max_subscriptions_per_project" in config:
            object.__setattr__(
                self,
                "max_subscriptions_per_project",
                int(config["max_subscriptions_per_project"]),
            )
        if "admin_notification_email" in config:
            object.__setattr__(
                self,
                "admin_notification_email",
                str(config["admin_notification_email"]),
            )
        if "subscription_approval_required" in config:
            object.__setattr__(
                self,
                "subscription_approval_required",
                bool(config["subscription_approval_required"]),
            )


settings = Settings()
