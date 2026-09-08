"""Chat API 模块迁移测试。"""

from pathlib import Path

import app
from fastapi import FastAPI
from app.api.v1.router import router as api_v1_router
from app.modules.chat.api import router as chat_router


def test_chat_router_keeps_existing_public_endpoint() -> None:
    """验证迁移后的 Chat 路由继续公开原有接口。"""
    application = FastAPI()
    application.include_router(chat_router)
    assert set(application.openapi()["paths"]["/api/v1/agent/chat"]) == {"post"}
    assert any(
        getattr(route, "original_router", None) is chat_router
        for route in api_v1_router.routes
    )


def test_application_has_no_legacy_chat_api_module_or_import() -> None:
    """验证旧 Chat API 文件和导入路径已经删除。"""
    app_root = Path(app.__file__).parent
    violations = [
        str(source_file.relative_to(app_root))
        for source_file in app_root.rglob("*.py")
        if "app.api.v1.agent" in source_file.read_text(encoding="utf-8")
    ]

    assert not violations
    assert not (app_root / "api" / "v1" / "agent.py").exists()


def test_chat_aggregate_registers_each_business_endpoint_once() -> None:
    """按公开契约验证子路由完整性，避免依赖 FastAPI 内部的嵌套路由表示。"""
    application = FastAPI()
    application.include_router(chat_router)
    paths = application.openapi()["paths"]
    assert {path: set(methods) for path, methods in paths.items()} == {
        "/api/v1/agent/chat": {"post"},
        "/api/v1/agent/conversations": {"get", "post"},
        "/api/v1/agent/conversations/{conversation_id}": {"patch"},
        "/api/v1/agent/conversations/{conversation_id}/messages": {"get", "post"},
        "/api/v1/agent/conversations/{conversation_id}/learn": {"post"},
        "/api/v1/agent/context-entries": {"get"},
        "/api/v1/agent/context-entries/{entry_id}": {"patch"},
        "/api/v1/agent/context-entries/publish": {"post"},
        "/api/v1/agent/context-entries/changes": {"get"},
        "/api/v1/agent/learning-drafts": {"get"},
        "/api/v1/agent/learning-drafts/{draft_id}": {"get", "patch"},
        "/api/v1/agent/learning-drafts/{draft_id}/refine": {"post"},
        "/api/v1/agent/learning-drafts/{draft_id}/confirm": {"post"},
        "/api/v1/agent/learning-drafts/{draft_id}/rebase": {"post"},
        "/api/v1/agent/tools": {"get"},
        "/api/v1/agent/runs/{run_id}": {"get"},
    }
