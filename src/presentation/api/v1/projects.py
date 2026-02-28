"""Project routes — /api/v1/projects."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from src.application.commands.form_commands import UpdateFormSchemaCommand
from src.application.commands.project_commands import (
    CreateProjectCommand,
    DeleteProjectCommand,
    UpdateProjectCommand,
)
from src.application.queries.project_queries import ProjectListQuery
from src.application.services.form_service import FormService
from src.application.services.project_service import ProjectService
from src.domain.entities.form_schema import CustomField, FieldType
from src.domain.entities.project import ProjectImage
from src.domain.exceptions import AuthorizationError
from src.presentation.auth import CurrentUser, get_current_user
from src.presentation.dependencies import get_form_service, get_project_service
from src.presentation.envelope import envelope

logger = structlog.get_logger()
router = APIRouter(prefix="/projects", tags=["Projects"])


# ── Request models ────────────────────────────────────────────────────────────


class CreateProjectRequest(BaseModel):
    name: str
    description: str
    category: str
    start_date: str
    end_date: str
    max_participants: int
    notification_emails: list[str] = []
    rich_text: str | None = None
    image_url: str | None = None
    cloudfront_url: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    rich_text: str | None = None
    category: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    max_participants: int | None = None
    notification_emails: list[str] | None = None
    image_url: str | None = None
    cloudfront_url: str | None = None
    status: str | None = None
    is_enabled: bool | None = None


class UpdateFormSchemaRequest(BaseModel):
    fields: list[dict[str, Any]]


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_project(
    body: CreateProjectRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    image = None
    if body.image_url and body.cloudfront_url:
        image = ProjectImage(
            image_id="",
            filename=body.image_url,
            content_type="",
            cloudfront_url=body.cloudfront_url,
            uploaded_at="",
        )
    cmd = CreateProjectCommand(
        name=body.name,
        description=body.description,
        category=body.category,
        start_date=body.start_date,
        end_date=body.end_date,
        max_participants=body.max_participants,
        notification_emails=body.notification_emails,
        created_by=user.sub,
        rich_text=body.rich_text,
        image=image,
    )
    result = await service.create(cmd)
    return envelope(asdict(result))


@router.get("/public")
async def list_public_projects(
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    projects = await service.list_public()
    return envelope([asdict(p) for p in projects])


@router.get("/")
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    if not user.is_admin:
        raise AuthorizationError(
            message=f"User {user.sub} attempted admin list without admin role",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )
    query = ProjectListQuery(
        page=page,
        page_size=page_size,
        status=status_filter,
        category=category,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    projects, total = await service.list_all(query)
    return envelope(
        {
            "items": [asdict(p) for p in projects],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{project_id}/enhanced")
async def get_project_enhanced(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    result = await service.get(project_id)
    return envelope(asdict(result))


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    result = await service.get(project_id)
    return envelope(asdict(result))


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> dict[str, Any]:
    image = None
    if body.image_url and body.cloudfront_url:
        image = ProjectImage(
            image_id="",
            filename=body.image_url,
            content_type="",
            cloudfront_url=body.cloudfront_url,
            uploaded_at="",
        )
    cmd = UpdateProjectCommand(
        project_id=project_id,
        requester_id=user.sub,
        is_admin=user.is_admin,
        name=body.name,
        description=body.description,
        rich_text=body.rich_text,
        category=body.category,
        start_date=body.start_date,
        end_date=body.end_date,
        max_participants=body.max_participants,
        notification_emails=body.notification_emails,
        image=image,
        status=body.status,
        is_enabled=body.is_enabled,
    )
    result = await service.update(cmd)
    return envelope(asdict(result))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> None:
    cmd = DeleteProjectCommand(
        project_id=project_id,
        requester_id=user.sub,
        is_admin=user.is_admin,
    )
    await service.delete(cmd)


@router.put("/{project_id}/form-schema")
async def update_form_schema(
    project_id: str,
    body: UpdateFormSchemaRequest,
    user: CurrentUser = Depends(get_current_user),
    form_service: FormService = Depends(get_form_service),
) -> dict[str, Any]:
    fields = [
        CustomField(
            id=f["id"],
            field_type=FieldType(f["field_type"]),
            question=f["question"],
            required=f.get("required", False),
            options=f.get("options", []),
        )
        for f in body.fields
    ]
    cmd = UpdateFormSchemaCommand(
        project_id=project_id,
        requester_id=user.sub,
        is_admin=user.is_admin,
        fields=fields,
    )
    result = await form_service.update_schema(cmd)
    return envelope(asdict(result))
