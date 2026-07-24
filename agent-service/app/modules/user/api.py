"""用户 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiResponse, success
from app.core.security import (
    AuthPrincipal,
    PasswordManager,
    get_password_manager,
    require_principal,
)
from app.infrastructure.database import get_db_session
from app.modules.user.repository import UserRepository
from app.modules.user.schemas import (
    ChangePasswordRequest,
    UpdateUserProfileRequest,
)
from app.modules.user.service import UserService

router = APIRouter(prefix="/api/v1/users", tags=["用户"])


def get_user_service(
    session: AsyncSession = Depends(get_db_session),
    password_manager: PasswordManager = Depends(get_password_manager),
) -> UserService:
    return UserService(UserRepository(session), password_manager)


@router.get("/me", response_model=ApiResponse)
async def me(
    principal: AuthPrincipal = Depends(require_principal),
    service: UserService = Depends(get_user_service),
) -> ApiResponse:
    return success(await service.get_profile(principal.user_id))


@router.put("/me", response_model=ApiResponse)
async def update_me(
    request: UpdateUserProfileRequest,
    principal: AuthPrincipal = Depends(require_principal),
    service: UserService = Depends(get_user_service),
) -> ApiResponse:
    return success(await service.update_profile(principal.user_id, request))


@router.put("/me/password", response_model=ApiResponse)
async def change_password(
    request: ChangePasswordRequest,
    principal: AuthPrincipal = Depends(require_principal),
    service: UserService = Depends(get_user_service),
) -> ApiResponse:
    await service.change_password(principal.user_id, request)
    return success()
