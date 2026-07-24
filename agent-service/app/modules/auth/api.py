"""认证 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.response import ApiResponse, success
from app.core.security import (
    AuthPrincipal,
    JwtManager,
    PasswordManager,
    get_jwt_manager,
    get_password_manager,
    require_principal,
)
from app.infrastructure.database import get_db_session
from app.infrastructure.redis import SessionStore, get_session_store
from app.modules.auth.schemas import LoginRequest, RegisterRequest
from app.modules.auth.service import AuthService
from app.modules.user.repository import UserRepository
from app.modules.user.service import UserService

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    password_manager: PasswordManager = Depends(get_password_manager),
    jwt_manager: JwtManager = Depends(get_jwt_manager),
    sessions: SessionStore = Depends(get_session_store),
) -> AuthService:
    users = UserService(UserRepository(session), password_manager)
    return AuthService(users, jwt_manager, sessions)


@router.post("/register", response_model=ApiResponse)
async def register(
    request: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse:
    return success(await service.register(request))


@router.post("/login", response_model=ApiResponse)
async def login(
    request: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse:
    return success(await service.login(request))


@router.post("/logout", response_model=ApiResponse)
async def logout(
    principal: AuthPrincipal = Depends(require_principal),
    service: AuthService = Depends(get_auth_service),
) -> ApiResponse:
    await service.logout(principal.jti)
    return success()
