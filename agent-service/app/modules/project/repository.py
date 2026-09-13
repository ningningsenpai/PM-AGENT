"""项目数据访问。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.project.domain import ProjectRecordStatus
from app.modules.project.models import Project


class ProjectRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, project_id: int) -> Project | None:
        return await self.session.get(Project, project_id)

    async def find_enabled_by_owner_and_name(
        self,
        owner_user_id: int,
        project_name: str,
    ) -> Project | None:
        statement = (
            select(Project)
            .where(
                Project.owner_user_id == owner_user_id,
                Project.project_name == project_name,
                Project.record_status == ProjectRecordStatus.ENABLED.value,
            )
            .limit(1)
        )
        return (await self.session.scalars(statement)).first()

    async def list_by_owner(self, owner_user_id: int) -> list[Project]:
        statement = (
            select(Project)
            .where(
                Project.owner_user_id == owner_user_id,
                Project.record_status == ProjectRecordStatus.ENABLED.value,
            )
            .order_by(Project.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def list_purge_due(self, now: datetime) -> list[Project]:
        statement = (
            select(Project)
            .where(
                Project.record_status == ProjectRecordStatus.DISABLED.value,
                Project.purge_after.is_not(None),
                Project.purge_after <= now,
            )
            .order_by(Project.purge_after.asc(), Project.id.asc())
        )
        return list((await self.session.scalars(statement)).all())

    async def delete_purge_due(self, project_id: int, now: datetime) -> bool:
        statement = (
            delete(Project)
            .where(
                Project.id == project_id,
                Project.record_status == ProjectRecordStatus.DISABLED.value,
                Project.purge_after.is_not(None),
                Project.purge_after <= now,
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(statement)
        return result.rowcount == 1

    async def advance_published_revision(self, project_id: int) -> int | None:
        """仅在没有未发布修订时原子推进项目发布修订。"""
        statement = (
            update(Project)
            .where(
                Project.id == project_id,
                Project.revision == Project.published_revision,
            )
            .values(
                revision=Project.revision + 1,
                published_revision=Project.published_revision + 1,
            )
            .execution_options(synchronize_session=False)
        )
        result = await self.session.execute(statement)
        if result.rowcount != 1:
            return None
        return await self.session.scalar(
            select(Project.published_revision).where(Project.id == project_id)
        )

    async def add(self, project: Project) -> Project:
        self.session.add(project)
        await self.session.flush()
        return project
