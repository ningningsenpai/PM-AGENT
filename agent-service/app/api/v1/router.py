"""V1 API 路由聚合。"""

from fastapi import APIRouter

from app.modules.auth.api import router as auth_router
from app.modules.chat.api import router as chat_router
from app.modules.project.api import router as project_router
from app.modules.project_file.api import router as project_file_router
from app.modules.user.api import router as user_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(user_router)
router.include_router(project_router)
router.include_router(project_file_router)
router.include_router(chat_router)
