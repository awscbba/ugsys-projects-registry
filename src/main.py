"""Composition root — wires all dependencies and creates the FastAPI application.

Call order:
1. configure_logging() — must be first
2. lifespan() — wires all repos, services, adapters
3. create_app() — registers middleware, exception handlers, routers
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aioboto3
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import SERVICE_CONFIG_SCHEMA, SERVICE_ROLES, settings
from src.infrastructure.logging import configure_logging

# configure_logging MUST be called before any other imports that use structlog
configure_logging(settings.service_name, settings.log_level)

logger = structlog.get_logger()

# X-Ray patching — must happen before boto3 clients are created
if settings.xray_tracing_enabled:
    try:
        from aws_xray_sdk.core import patch_all, xray_recorder

        xray_recorder.configure(
            sampling=True,
            sampling_rules={
                "default": {
                    "fixed_target": 1,
                    "rate": settings.xray_sampling_rate,
                }
            },
        )
        patch_all()
        logger.info("xray.patching_enabled", sampling_rate=settings.xray_sampling_rate)
    except ImportError:
        pass

from ugsys_auth_client import TokenValidator
from ugsys_auth_client.auth_middleware import AuthMiddleware

from src.application.services.admin_service import AdminService
from src.application.services.event_consumer_service import EventConsumerService
from src.application.services.form_service import FormService
from src.application.services.image_service import ImageService
from src.application.services.project_service import ProjectService
from src.application.services.public_service import PublicService
from src.application.services.subscription_service import SubscriptionService
from src.domain.exceptions import DomainError
from src.infrastructure.adapters.identity_manager_client import IdentityManagerClient
from src.infrastructure.adapters.in_memory_circuit_breaker import InMemoryCircuitBreaker
from src.infrastructure.adapters.s2s_token_provider import S2STokenProvider
from src.infrastructure.adapters.s3_client import S3ClientAdapter
from src.infrastructure.messaging.event_publisher import EventBridgePublisher
from src.infrastructure.persistence.dynamodb_form_submission_repository import (
    DynamoDBFormSubmissionRepository,
)
from src.infrastructure.persistence.dynamodb_project_repository import DynamoDBProjectRepository
from src.infrastructure.persistence.dynamodb_subscription_repository import (
    DynamoDBSubscriptionRepository,
)
from src.presentation.api.v1 import (
    admin,
    form_submissions,
    health,
    images,
    projects,
    public,
    subscriptions,
)
from src.presentation.event_consumer import set_event_consumer_service
from src.presentation.middleware.correlation_id import CorrelationIdMiddleware
from src.presentation.middleware.exception_handler import (
    domain_exception_handler,
    unhandled_exception_handler,
)
from src.presentation.middleware.rate_limiting import RateLimitMiddleware
from src.presentation.middleware.security_headers import SecurityHeadersMiddleware
from src.presentation.middleware.xray_middleware import XRayMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info("startup.begin", service=settings.service_name, version=settings.version)

    session = aioboto3.Session()

    async with (
        session.client("dynamodb", region_name=settings.aws_region) as dynamodb,
        session.client("events", region_name=settings.aws_region) as eventbridge,
        session.client("s3", region_name=settings.aws_region) as s3,
    ):
        # ── Repositories ──────────────────────────────────────────────────────
        project_repo = DynamoDBProjectRepository(
            table_name=settings.projects_table_name,
            client=dynamodb,
        )
        subscription_repo = DynamoDBSubscriptionRepository(
            table_name=settings.subscriptions_table_name,
            client=dynamodb,
        )
        form_submission_repo = DynamoDBFormSubmissionRepository(
            table_name=settings.form_submissions_table_name,
            client=dynamodb,
        )

        # ── Infrastructure adapters ───────────────────────────────────────────
        event_publisher = EventBridgePublisher(
            event_bus_name=settings.event_bus_name,
            client=eventbridge,
        )
        s3_adapter = S3ClientAdapter(
            bucket_name=settings.images_bucket_name,
            client=s3,
        )

        # ── Identity Manager client with circuit breaker ──────────────────────
        circuit_breaker = InMemoryCircuitBreaker(
            service_name="identity-manager",
            failure_threshold=5,
            cooldown_seconds=30,
        )
        token_url = (
            f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}/oauth2/token"
        )
        s2s_token_provider = S2STokenProvider(
            token_url=token_url,
            client_id=settings.identity_manager_client_id,
            client_secret=settings.identity_manager_client_secret,
        )
        identity_client = IdentityManagerClient(
            base_url=settings.identity_manager_url,
            s2s_token_provider=s2s_token_provider,
            circuit_breaker=circuit_breaker,
        )

        # ── Application services ──────────────────────────────────────────────
        project_service = ProjectService(
            project_repo=project_repo,
            subscription_repo=subscription_repo,
            event_publisher=event_publisher,
        )
        subscription_service = SubscriptionService(
            subscription_repo=subscription_repo,
            project_repo=project_repo,
            event_publisher=event_publisher,
        )
        form_service = FormService(
            project_repo=project_repo,
            form_submission_repo=form_submission_repo,
        )
        public_service = PublicService(
            identity_client=identity_client,
            subscription_repo=subscription_repo,
            project_repo=project_repo,
            event_publisher=event_publisher,
        )
        admin_service = AdminService(
            project_repo=project_repo,
            subscription_repo=subscription_repo,
            form_submission_repo=form_submission_repo,
            identity_client=identity_client,
        )
        image_service = ImageService(
            s3_client=s3_adapter,
            cloudfront_base_url=f"https://{settings.cloudfront_domain}",
        )
        event_consumer_service = EventConsumerService(
            subscription_repo=subscription_repo,
            event_publisher=event_publisher,
        )

        # ── Store services on app.state ───────────────────────────────────────
        app.state.project_service = project_service
        app.state.subscription_service = subscription_service
        app.state.form_service = form_service
        app.state.public_service = public_service
        app.state.admin_service = admin_service
        app.state.image_service = image_service
        app.state.event_consumer_service = event_consumer_service

        # ── Token validator — store on app.state for auth-client get_current_user ──
        app.state.token_validator = _token_validator

        # ── Inject into event consumer Lambda handler ─────────────────────────
        set_event_consumer_service(event_consumer_service)

        # ── Service registration (non-fatal) ──────────────────────────────────
        try:
            await identity_client.register_service(
                service_id=settings.service_id,
                display_name=settings.display_name,
                version=settings.version,
                nav_icon=settings.nav_icon,
                health_url=f"{settings.public_base_url}/health",
                config_schema=SERVICE_CONFIG_SCHEMA,
                roles=SERVICE_ROLES,
            )
            logger.info("startup.service_registered", service_id=settings.service_id)
        except Exception as exc:
            logger.warning(
                "startup.service_registration_failed",
                service_id=settings.service_id,
                error=str(exc),
            )

        # ── Remote config (non-fatal) ─────────────────────────────────────────
        try:
            remote_config = await identity_client.get_service_config(settings.service_id)
            settings.apply_remote_config(remote_config)
            logger.info("startup.remote_config_applied", service_id=settings.service_id)
        except Exception as exc:
            logger.warning(
                "startup.remote_config_failed",
                service_id=settings.service_id,
                error=str(exc),
            )

        logger.info("startup.complete", service=settings.service_name)
        yield

    logger.info("shutdown.complete", service=settings.service_name)


# TokenValidator created at module level — construction is cheap (no I/O).
# JWKS keys are fetched lazily on first validation request.
# Uses identity-manager JWKS endpoint (RS256 tokens issued by ugsys-identity-manager).
_token_validator = TokenValidator(
    jwks_url=settings.jwks_url or None,
    jwt_algorithm="RS256",
)


def create_app() -> FastAPI:
    """Application factory — single composition root."""
    app = FastAPI(
        title=settings.service_name,
        version=settings.version,
        docs_url="/docs" if settings.environment != "prod" else None,
        redoc_url="/redoc" if settings.environment != "prod" else None,
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
    )

    # ── Middleware (last added = first executed) ───────────────────────────────
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
    app.add_middleware(AuthMiddleware, validator=_token_validator)
    if settings.xray_tracing_enabled:
        app.add_middleware(
            XRayMiddleware,
            service_name=settings.service_name,
            version=settings.version,
            environment=settings.environment,
        )

    # ── Exception handlers ────────────────────────────────────────────────────
    app.add_exception_handler(DomainError, domain_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(subscriptions.router, prefix="/api/v1")
    app.include_router(public.router, prefix="/api/v1")
    app.include_router(form_submissions.router, prefix="/api/v1")
    app.include_router(images.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    return app


app = create_app()
