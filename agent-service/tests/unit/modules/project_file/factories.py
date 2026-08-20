"""项目文件测试对象工厂。"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from types import SimpleNamespace

from app.core.config import StorageConfig
from app.modules.project_file.models import ProjectFile


def storage_config() -> StorageConfig:
    return StorageConfig(
        endpoint="127.0.0.1:9000",
        access_key="test",
        secret_key="test",
        secure=False,
        bucket="pm-agent-test",
        read_url_expiry_seconds=300,
    )


def project():
    return SimpleNamespace(
        id=10,
        owner_user_id=1,
        project_name="PM-Agent",
        created_at=datetime(2026, 7, 27, 9, 0, 0),
    )


def project_file(
    *,
    file_id: int = 30,
    business_code: str = "project",
    relative_path: str = "docs/README.md",
    file_name: str = "README.md",
    content: bytes = b"original content",
    status: str = "active",
    upload_status: str = "success",
    lock_version: int = 0,
) -> ProjectFile:
    file = ProjectFile(
        id=file_id,
        project_id=10,
        business_code=business_code,
        relative_path=relative_path,
        path_hash=sha256(relative_path.encode()).hexdigest(),
        file_name=file_name,
        extension="md",
        storage_uuid="a1b2c3d4e5f67890",
        storage_name="README-a1b2c3d4e5f67890.md",
        object_key="PM-AGENT/1/10/project/README-a1b2c3d4e5f67890.md",
        minio_path="project/README-a1b2c3d4e5f67890.md",
        content_type="text/markdown",
        size_bytes=len(content),
        source_mtime_ms=100,
        quick_fingerprint="a" * 64,
        content_hash=sha256(content).hexdigest(),
        status=status,
        upload_status=upload_status,
        upload_attempts=1,
        parse_attempts=0,
        detail_ref=None,
        module=None,
        kind=None,
        file_type=None,
        language=None,
        importance=None,
        summary=None,
        keywords=None,
        last_error_code=None,
        last_error_message=None,
        last_failed_at=None,
        lock_version=lock_version,
    )
    file.created_at = datetime(2026, 7, 27, 9, 0, 0)
    file.updated_at = datetime(2026, 7, 27, 9, 0, 0)
    return file
