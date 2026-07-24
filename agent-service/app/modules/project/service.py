"""项目生命周期服务。"""
from __future__ import annotations

import asyncio

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
)
from app.modules.project.domain import ProjectStatus
from app.modules.project.errors import (
    project_disabled,
    project_name_exists,
    project_not_found,
)
from app.modules.project.index_service import ProjectIndexService
from app.modules.project.models import Project
from app.modules.project.repository import ProjectRepository
from app.modules.project.schemas import (
    CreateProjectRequest,
    ProjectResponse,
    to_response,
)


class ProjectService:
    def __init__(
        self,
        repository: ProjectRepository,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        index_service: ProjectIndexService,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._locations = locations
        self._index = index_service

    async def create(
        self,
        owner_user_id: int,
        request: CreateProjectRequest,
    ) -> ProjectResponse:
        existing = await self._repository.find_by_owner_and_name(
            owner_user_id,
            request.project_name,
        )
        if existing is not None:
            if existing.status == ProjectStatus.ACTIVE.value:
                raise project_name_exists()
            if existing.status == ProjectStatus.INIT_FAILED.value:
                await self._index.initialize(existing)
                existing.status = ProjectStatus.ACTIVE.value
                await self._repository.session.commit()
                return to_response(existing)

        project = Project(
            owner_user_id=owner_user_id,
            project_name=request.project_name,
            status=ProjectStatus.INITIALIZING.value,
        )
        try:
            await self._repository.add(project)
            await self._repository.session.commit()
            await self._repository.session.refresh(project)
        except IntegrityError as exception:
            await self._repository.session.rollback()
            raise project_name_exists() from exception

        try:
            await self._index.initialize(project)
        except Exception:
            await self._repository.delete(project.id)
            await self._repository.session.commit()
            raise

        project.status = ProjectStatus.ACTIVE.value
        await self._repository.session.commit()
        await self._repository.session.refresh(project)
        return to_response(project)

    async def list_owned(self, owner_user_id: int) -> list[ProjectResponse]:
        projects = await self._repository.list_by_owner(owner_user_id)
        return [to_response(project) for project in projects]

    async def get_owned(
        self,
        owner_user_id: int,
        project_id: int,
    ) -> ProjectResponse:
        return to_response(await self.require_owned(owner_user_id, project_id))

    async def require_owned(self, owner_user_id: int, project_id: int) -> Project:
        project = await self._repository.get_by_id(project_id)
        if project is None or project.owner_user_id != owner_user_id:
            raise project_not_found()
        if project.status != ProjectStatus.ACTIVE.value:
            raise project_disabled()
        return project

    async def delete_owned(self, owner_user_id: int, project_id: int) -> None:
        project = await self.require_owned(owner_user_id, project_id)
        prefix = self._locations.project_prefix(project.owner_user_id, project.id)
        try:
            await asyncio.to_thread(self._storage.remove_prefix, prefix)
        except AppException as exception:
            raise AppException(ErrorCode.PROJECT_DELETE_FAILED) from exception
        try:
            await self._repository.delete(project.id)
            await self._repository.session.commit()
        except Exception as exception:
            await self._repository.session.rollback()
            raise AppException(ErrorCode.PROJECT_DELETE_FAILED) from exception
