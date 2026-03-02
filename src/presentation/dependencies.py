"""FastAPI dependency injection functions — read services from app.state."""

from __future__ import annotations

from fastapi import Request

from src.application.services.admin_service import AdminService
from src.application.services.event_consumer_service import EventConsumerService
from src.application.services.form_service import FormService
from src.application.services.image_service import ImageService
from src.application.services.project_service import ProjectService
from src.application.services.public_service import PublicService
from src.application.services.subscription_service import SubscriptionService


def get_project_service(request: Request) -> ProjectService:
    return request.app.state.project_service  # type: ignore[no-any-return]


def get_subscription_service(request: Request) -> SubscriptionService:
    return request.app.state.subscription_service  # type: ignore[no-any-return]


def get_form_service(request: Request) -> FormService:
    return request.app.state.form_service  # type: ignore[no-any-return]


def get_public_service(request: Request) -> PublicService:
    return request.app.state.public_service  # type: ignore[no-any-return]


def get_admin_service(request: Request) -> AdminService:
    return request.app.state.admin_service  # type: ignore[no-any-return]


def get_image_service(request: Request) -> ImageService:
    return request.app.state.image_service  # type: ignore[no-any-return]


def get_event_consumer_service(request: Request) -> EventConsumerService:
    return request.app.state.event_consumer_service  # type: ignore[no-any-return]
