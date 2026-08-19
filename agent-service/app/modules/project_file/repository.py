"""项目文件数据访问。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.project_file.models import ProjectFile


class ProjectFileRepository:
    MAX_PARSE_ATTEMPTS = 3

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, project_id: int, file_id: int) -> ProjectFile | None:
        statement = (
            select(ProjectFile)
            .where(
                ProjectFile.id == file_id,
                ProjectFile.project_id == project_id,
            )
            .limit(1)
        )
        return (await self.session.scalars(statement)).first()

    async def find_path(
        self,
        project_id: int,
        business_code: str,
        path_hash: str,
    ) -> ProjectFile | None:
        statement = (
            select(ProjectFile)
            .where(
                ProjectFile.project_id == project_id,
                ProjectFile.business_code == business_code,
                ProjectFile.path_hash == path_hash,
            )
            .limit(1)
        )
        return (await self.session.scalars(statement)).first()

    async def list(
        self,
        project_id: int,
        business_code: str | None = None,
        *,
        include_system: bool = False,
    ) -> list[ProjectFile]:
        statement = select(ProjectFile).where(ProjectFile.project_id == project_id)
        if business_code:
            statement = statement.where(ProjectFile.business_code == business_code)
        elif not include_system:
            statement = statement.where(ProjectFile.business_code != "system")
        statement = statement.order_by(
            ProjectFile.relative_path.asc()
        ).execution_options(populate_existing=True)
        return list((await self.session.scalars(statement)).all())

    async def list_parse_candidates(
        self,
        project_id: int,
        target_version: str,
    ) -> list[ProjectFile]:
        """获取未解析、失败重试或需要升级分析版本的文件。"""
        statement = (
            select(ProjectFile)
            .where(
                ProjectFile.project_id == project_id,
                or_(
                    ProjectFile.analysis_version.is_(None),
                    ProjectFile.analysis_version != target_version,
                ),
                or_(
                    ProjectFile.parse_attempts < self.MAX_PARSE_ATTEMPTS,
                    and_(
                        ProjectFile.analysis_version.is_not(None),
                        ProjectFile.analysis_version != target_version,
                        ProjectFile.last_error_code.is_(None),
                    ),
                ),
                ProjectFile.status == "active",
                ProjectFile.upload_status == "success",
                ProjectFile.business_code != "system",
            )
            .order_by(ProjectFile.relative_path.asc())
        )
        return list((await self.session.scalars(statement)).all())

    async def add(self, file: ProjectFile) -> ProjectFile:
        self.session.add(file)
        await self.session.flush()
        return file

    async def delete(self, file_id: int) -> None:
        await self.session.execute(delete(ProjectFile).where(ProjectFile.id == file_id))

    async def claim_state(
        self,
        project_id: int,
        file_id: int,
        expected_lock_version: int,
        expected_statuses: tuple[str, ...],
        target_status: str,
    ) -> bool:
        statement = (
            update(ProjectFile)
            .where(
                ProjectFile.id == file_id,
                ProjectFile.project_id == project_id,
                ProjectFile.status.in_(expected_statuses),
                ProjectFile.lock_version == expected_lock_version,
            )
            .values(
                status=target_status,
                lock_version=expected_lock_version + 1,
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(statement)
        return result.rowcount == 1

    async def record_analysis_success(
        self,
        project_id: int,
        file_id: int,
        content_hash: str,
        detail,
    ) -> bool:
        statement = (
            update(ProjectFile)
            .where(
                ProjectFile.id == file_id,
                ProjectFile.project_id == project_id,
                ProjectFile.content_hash == content_hash,
            )
            .values(
                parse_attempts=ProjectFile.parse_attempts + 1,
                detail_ref=detail.detail_ref,
                analysis_version=detail.analysis_version,
                module=detail.module,
                kind=detail.kind,
                file_type=detail.file_type,
                language=detail.language,
                importance=detail.importance,
                summary=detail.summary,
                keywords=detail.keywords,
                last_error_code=None,
                last_error_message=None,
                last_failed_at=None,
            )
        )
        result = await self.session.execute(statement)
        return result.rowcount == 1

    async def record_analysis_failure(
        self,
        project_id: int,
        file_id: int,
        content_hash: str,
        error_code: str,
        error_message: str,
    ) -> bool:
        statement = (
            update(ProjectFile)
            .where(
                ProjectFile.id == file_id,
                ProjectFile.project_id == project_id,
                ProjectFile.content_hash == content_hash,
            )
            .values(
                parse_attempts=ProjectFile.parse_attempts + 1,
                last_error_code=error_code[:64],
                last_error_message=error_message[:500],
                last_failed_at=datetime.now(),
            )
        )
        result = await self.session.execute(statement)
        return result.rowcount == 1
