"""项目文件分析测试对象工厂。"""

from datetime import datetime

from app.modules.project_file.models import ProjectFile
from app.project.context.detail_analysis.schemas import FileDetail


def file_detail(file: ProjectFile) -> FileDetail:
    """构造文件分析详情。"""
    generated_at = datetime(2026, 7, 27, 10, 0, 0)
    return FileDetail(
        id=f"file-{file.id}",
        project_id=file.project_id,
        file_id=file.id,
        schema_version="1.0.0",
        analysis_version="file-detail-v1",
        generated_at=generated_at,
        updated_at=generated_at,
        storage_uuid=file.storage_uuid,
        storage_name=file.storage_name,
        detail_ref="system/file_details/README-a1b2c3d4e5f67890.json",
        original_path=file.relative_path,
        minio_path=file.minio_path,
        size_bytes=file.size_bytes,
        content_type=file.content_type,
        content_hash=file.content_hash,
        module="docs",
        kind="documentation",
        file_type="doc",
        language="markdown",
        status="active",
        importance="medium",
        summary="项目说明",
        keywords=["项目"],
        role="说明项目结构",
        content_slices=[],
        related_topics=[],
        related_files=[],
        risk_flags=[],
        sensitive_flags=[],
        evidence=[],
        previous_versions=[],
        parser={"strategy": "llm_enhanced"},
    )
