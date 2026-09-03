"""项目数据访问。"""

from __future__ import annotations

from sqlalchemy import select
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

    async def add(self, project: Project) -> Project:
        self.session.add(project)
        await self.session.flush()
        return project
