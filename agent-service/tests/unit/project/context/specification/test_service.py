"""项目规范构建服务单元测试。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from app.infrastructure.storage import StorageLocationFactory
from app.project.context.specification.schemas import (
    DevelopmentApproachRule,
    ProjectSpecificationBody,
    ProjectSpecificationDocument,
    merge_specifications,
)
from app.project.context.specification.service import ProjectSpecificationService
from tests.unit.modules.project_file.factories import (
    project,
    project_file,
    storage_config,
)


def _document(rule_text: str, *, include_rule: bool = True):
    now = datetime(2026, 8, 3, 10, 0, 0)
    rules = []
    if include_rule:
        rules.append(
            DevelopmentApproachRule(
                id="development-approach-1",
                rule=rule_text,
                scope="global",
                status="active",
                confidence="high",
                created_at=now,
                updated_at=now,
            )
        )
    return ProjectSpecificationDocument(
        project_id=10,
        updated_at=now,
        project_specification=ProjectSpecificationBody(
            development_approach=rules,
        ),
    )


class ProjectSpecificationServiceTest(IsolatedAsyncioTestCase):
    def test_merge_preserves_omitted_rules_and_updates_same_id(self) -> None:
        existing = _document("旧规则")
        updated = merge_specifications(existing, _document("新规则"))
        omitted = merge_specifications(
            existing,
            _document("", include_rule=False),
        )

        self.assertEqual(
            "新规则",
            updated.project_specification.development_approach[0].rule,
        )
        self.assertEqual(
            "旧规则",
            omitted.project_specification.development_approach[0].rule,
        )

    async def test_refresh_generates_and_stores_specification(self) -> None:
        storage = Mock()
        storage.exists.return_value = False
        generator = SimpleNamespace(generate=AsyncMock(return_value=_document("新规则")))
        service = ProjectSpecificationService(
            storage,
            StorageLocationFactory(storage_config()),
            generator,
        )
        file = project_file()
        file.analysis_version = "file-detail-v1"
        file.summary = "项目采用 FastAPI 单体架构"
        file.importance = "high"

        await service.refresh(project(), [file])

        generator.generate.assert_awaited_once()
        storage.put_bytes.assert_called_once()
        location, content, content_type = storage.put_bytes.call_args.args
        self.assertTrue(location.object_key.endswith("system/project_specification.json"))
        self.assertIn("新规则".encode(), content)
        self.assertEqual("application/json", content_type)
