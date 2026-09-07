"""真实行范围、限长与对象哈希的证据读取约束。"""
import hashlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.errors import AppException
from app.infrastructure.storage import StorageLocationFactory
from app.modules.project_file.management.service import ProjectFileService

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def service(text):
    raw = text.encode()
    file = SimpleNamespace(id=5, business_code="project", status="active", upload_status="success", object_key="PM-AGENT/1/11/project/source.py", file_name="source.py", content_type="text/plain", content_hash=hashlib.sha256(raw).hexdigest(), relative_path="source.py")
    repository = SimpleNamespace(get=AsyncMock(return_value=file), session=SimpleNamespace(commit=AsyncMock()))
    storage = SimpleNamespace(read_bytes=Mock(return_value=raw))
    value = ProjectFileService(repository, SimpleNamespace(require_owned=AsyncMock()), storage, StorageLocationFactory(SimpleNamespace(bucket="test")), None, None, None, None)
    return value, file, storage


async def test_evidence_actual_range_and_hash():
    source = "第一行\n第二行\n第三行\n"
    value, file, _ = service(source)
    with patch("app.project_context.file_detail.extraction.FileContentExtractionService.extract_from_bytes", new=AsyncMock(return_value={"text":source})):
        evidence = await value.read_evidence(1, 11, 5, 2, 200)
    assert evidence["text"] == "2: 第二行\n3: 第三行"
    assert evidence["startLine"] == 2 and evidence["endLine"] == 3
    assert evidence["contentHash"] == file.content_hash
    value._repository.session.commit.assert_awaited_once()


async def test_evidence_limits_and_foreign_object_refused():
    value, file, storage = service("原文")
    with pytest.raises(AppException, match="200 行"):
        await value.read_evidence(1, 11, 5, 1, 201)
    file.object_key = "PM-AGENT/2/21/project/source.py"
    with pytest.raises(AppException, match="不属于"):
        await value.read_evidence(1, 11, 5)
    storage.read_bytes.assert_not_called()


async def test_changed_source_hash_is_not_presented_as_current_evidence():
    value, _, storage = service("原文")
    storage.read_bytes.return_value = b"changed"
    with pytest.raises(AppException, match="哈希"):
        await value.read_evidence(1, 11, 5)


async def test_long_line_truncated_and_credentials_redacted():
    source = "password='synthetic-password'\n" + "中文" * 20000
    value, _, _ = service(source)
    with patch("app.project_context.file_detail.extraction.FileContentExtractionService.extract_from_bytes", new=AsyncMock(return_value={"text":source})):
        evidence = await value.read_evidence(1, 11, 5)
    assert evidence["truncated"] and evidence["redacted"]
    assert len(evidence["text"].encode()) <= 32768
    assert "synthetic-password" not in evidence["text"]
