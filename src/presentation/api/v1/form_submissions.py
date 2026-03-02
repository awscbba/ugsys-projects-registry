"""Form submission routes — /api/v1/form-submissions."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import structlog
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from src.application.commands.form_commands import SubmitFormCommand
from src.application.services.form_service import FormService
from src.domain.exceptions import AuthorizationError
from src.presentation.auth import CurrentUser, get_current_user
from src.presentation.dependencies import get_form_service
from src.presentation.envelope import envelope

logger = structlog.get_logger()
router = APIRouter(prefix="/form-submissions", tags=["Form Submissions"])


class SubmitFormRequest(BaseModel):
    project_id: str
    responses: dict[str, Any]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_form(
    body: SubmitFormRequest,
    user: CurrentUser = Depends(get_current_user),
    service: FormService = Depends(get_form_service),
) -> dict[str, Any]:
    cmd = SubmitFormCommand(
        project_id=body.project_id,
        person_id=user.sub,
        responses=body.responses,
    )
    result = await service.submit(cmd)
    return envelope(asdict(result))


@router.get("/project/{project_id}")
async def list_project_submissions(
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: FormService = Depends(get_form_service),
) -> dict[str, Any]:
    if not user.is_admin:
        raise AuthorizationError(
            message=f"User {user.sub} lacks admin role for form submission listing",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )
    submissions = await service.list_by_project(project_id)
    return envelope([asdict(s) for s in submissions])


@router.get("/person/{person_id}/project/{project_id}")
async def get_person_submission(
    person_id: str,
    project_id: str,
    user: CurrentUser = Depends(get_current_user),
    service: FormService = Depends(get_form_service),
) -> dict[str, Any]:
    if not user.is_admin and user.sub != person_id:
        raise AuthorizationError(
            message=f"User {user.sub} attempted IDOR on submission for person {person_id}",
            user_message="Access denied",
            error_code="FORBIDDEN",
        )
    result = await service.get_submission(
        submission_id="",
        person_id=person_id,
        project_id=project_id,
        is_admin=user.is_admin,
    )
    return envelope(asdict(result))
