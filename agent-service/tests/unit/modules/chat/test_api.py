"""Chat API 模块迁移测试。"""

from pathlib import Path

import app
from app.api.v1.router import router as api_v1_router
from app.modules.chat.api import router as chat_router


def test_chat_router_keeps_existing_public_endpoint() -> None:
    """验证迁移后的 Chat 路由继续公开原有接口。"""
    routes = [
        route
        for route in chat_router.routes
        if getattr(route, "path", None) == "/api/v1/agent/chat"
    ]

    assert len(routes) == 1
    assert "POST" in routes[0].methods
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
