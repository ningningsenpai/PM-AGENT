"""无外部服务的在线业务主链路集成测试。"""
from __future__ import annotations

import asyncio
from datetime import datetime
import json

from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.infrastructure.database import Base, get_db_session
from app.infrastructure.redis import RedisProvider, get_redis_provider
from app.infrastructure.storage import (
    StorageLocation,
    StorageLocationFactory,
    get_object_storage,
)
from app.main import app
from app.modules.project.index_service import ProjectIndexService
from app.modules.project.repository import ProjectRepository
from app.modules.project.service import ProjectService
from app.modules.project_file.analysis_service import ProjectFileAnalysisService
from app.modules.project_file.api import get_project_file_analysis_service
from app.modules.project_file.repository import ProjectFileRepository
from app.project.context.detail_analysis.schemas import (
    FileAnalysisRequest,
    FileAnalysisResult,
    FileDetail,
)


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    async def set(
        self,
        key: str,
        value: str,
        *,
        ex: int | None = None,
        nx: bool = False,
    ) -> bool:
        del ex
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)


class FakeObjectStorage:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_bytes(
        self,
        location: StorageLocation,
        content: bytes,
        content_type: str,
    ) -> None:
        del content_type
        self.objects[(location.bucket, location.object_key)] = content

    def get_bytes(self, location: StorageLocation) -> bytes:
        return self.objects[(location.bucket, location.object_key)]

    def copy(
        self,
        source: StorageLocation,
        target: StorageLocation,
    ) -> None:
        self.objects[(target.bucket, target.object_key)] = self.get_bytes(source)

    def remove(self, location: StorageLocation) -> None:
        self.objects.pop((location.bucket, location.object_key), None)

    def remove_prefix(self, location: StorageLocation) -> None:
        for key in list(self.objects):
            if key[0] == location.bucket and key[1].startswith(location.object_key):
                del self.objects[key]

    def presigned_get(self, location: StorageLocation) -> str:
        return f"http://minio.local/{location.bucket}/{location.object_key}"


class FakeAnalyzer:
    async def analyze_bytes(
        self,
        request: FileAnalysisRequest,
        content: bytes,
    ) -> FileAnalysisResult:
        assert content == b"# PM-Agent"
        now = datetime.now()
        detail = FileDetail(
            id=f"file-{request.file_id}",
            project_id=request.project_id,
            file_id=request.file_id,
            schema_version="1.0.0",
            analysis_version=request.analysis_version,
            generated_at=now,
            updated_at=now,
            storage_uuid=request.storage_uuid,
            storage_name=request.storage_name,
            detail_ref=request.detail_ref,
            original_path=request.original_path,
            minio_path=request.minio_path,
            size_bytes=request.size_bytes,
            content_type=request.content_type,
            content_hash=request.content_hash,
            module="docs",
            kind="documentation",
            file_type="doc",
            language="markdown",
            status="active",
            importance="medium",
            summary="项目说明",
            keywords=["PM-Agent"],
            role="项目说明",
            content_slices=[],
            related_topics=[],
            related_files=[],
            risk_flags=[],
            sensitive_flags=[],
            evidence=[],
            previous_versions=[],
            parser={"strategy": "fake"},
        )
        return FileAnalysisResult(
            project_id=request.project_id,
            file_id=request.file_id,
            content_hash=request.content_hash,
            analysis_version=request.analysis_version,
            status="success",
            detail=detail,
        )


def test_register_project_upload_parse_and_logout_flow() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    redis_provider = RedisProvider(FakeRedisClient(), "test")
    storage = FakeObjectStorage()

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_session():
        async with session_factory() as session:
            yield session

    def override_analysis_service(
        session: AsyncSession = Depends(get_db_session),
    ) -> ProjectFileAnalysisService:
        locations = StorageLocationFactory(get_settings().storage)
        index_service = ProjectIndexService(storage, locations)
        projects = ProjectService(
            ProjectRepository(session),
            storage,
            locations,
            index_service,
        )
        return ProjectFileAnalysisService(
            ProjectFileRepository(session),
            projects,
            storage,
            locations,
            index_service,
            FakeAnalyzer(),
        )

    asyncio.run(prepare_database())
    app.dependency_overrides[get_db_session] = override_session
    app.dependency_overrides[get_redis_provider] = lambda: redis_provider
    app.dependency_overrides[get_object_storage] = lambda: storage
    app.dependency_overrides[
        get_project_file_analysis_service
    ] = override_analysis_service

    try:
        client = TestClient(app)
        register = client.post(
            "/api/v1/auth/register",
            json={
                "username": "tester",
                "email": "tester@example.com",
                "password": "Password123",
            },
            headers={"X-Trace-Id": "flow-register"},
        )
        assert register.json()["code"] == 0
        token = register.json()["data"]["tokenValue"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Trace-Id": "flow-test",
        }

        me = client.get("/api/v1/users/me", headers=headers)
        assert me.json()["data"]["email"] == "tester@example.com"

        created = client.post(
            "/api/v1/projects",
            json={"projectName": "Python 迁移项目"},
            headers=headers,
        )
        assert created.json()["code"] == 0
        project_id = created.json()["data"]["id"]

        uploaded = client.post(
            f"/api/v1/projects/{project_id}/files",
            data={
                "relativePath": "docs/README.md",
                "sourceMtimeMs": "100",
            },
            files={"file": ("README.md", b"# PM-Agent", "text/markdown")},
            headers={**headers, "X-Idempotency-Key": "flow-upload-1"},
        )
        assert uploaded.json()["data"]["status"] == "active"
        assert uploaded.json()["data"]["uploadStatus"] == "success"

        parsed = client.post(
            f"/api/v1/projects/{project_id}/files/parse/init",
            headers=headers,
        )
        assert parsed.json()["code"] == 0

        files = client.get(
            f"/api/v1/projects/{project_id}/files",
            headers=headers,
        )
        assert files.json()["data"][0]["parseAttempts"] == 1

        settings = get_settings().storage
        index_key = (
            settings.bucket,
            f"PM-AGENT/1/{project_id}/system/index.json",
        )
        index = json.loads(storage.objects[index_key])
        assert index["project"][0]["summary"] == "项目说明"
        assert index["project"][0]["detail_ref"].startswith(
            "system/file_details/"
        )

        logout = client.post("/api/v1/auth/logout", headers=headers)
        assert logout.json()["code"] == 0
        expired = client.get("/api/v1/users/me", headers=headers)
        assert expired.json()["code"] == 20001
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
