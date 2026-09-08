"""Chat 路由聚合；具体业务接口由职责子包维护。"""

from fastapi import APIRouter

from .context.api import router as context_router
from .conversation.api import router as conversation_router
from .learning.api import router as learning_router
from .legacy.api import router as legacy_router
from .runs.api import router as run_router

router = APIRouter()
for child in (
    legacy_router,
    conversation_router,
    learning_router,
    context_router,
    run_router,
):
    router.include_router(child)
