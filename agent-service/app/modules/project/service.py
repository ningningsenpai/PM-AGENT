"""项目生命周期服务。"""
from __future__ import annotations

import asyncio

from sqlalchemy.exc import IntegrityError

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
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

logger = get_logger(__name__)


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
        logger.info("创建项目 action=project.create userId=%s", owner_user_id)
        existing = await self._repository.find_by_owner_and_name(
            owner_user_id,
            request.project_name,
        )
        if existing is not None:
            if existing.status == ProjectStatus.ACTIVE.value:
                raise project_name_exists()
            if existing.status == ProjectStatus.INIT_FAILED.value:
                logger.info(
                    "重试项目初始化 action=project.create userId=%s projectId=%s",
                    owner_user_id,
                    existing.id,
                )
                await self._index.initialize(existing)
                existing.status = ProjectStatus.ACTIVE.value
                await self._repository.session.commit()
                logger.info(
                    "项目创建成功 action=project.create userId=%s projectId=%s",
                    owner_user_id,
                    existing.id,
                )
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
            logger.exception(
                "项目记录创建失败 action=project.create userId=%s",
                owner_user_id,
            )
            raise project_name_exists() from exception

        try:
            await self._index.initialize(project)
        except Exception:
            logger.warning(
                "项目初始化失败，清理项目记录 action=project.create "
                "userId=%s projectId=%s",
                owner_user_id,
                project.id,
            )
            await self._repository.delete(project.id)
            await self._repository.session.commit()
            raise

        project.status = ProjectStatus.ACTIVE.value
        await self._repository.session.commit()
        await self._repository.session.refresh(project)
        logger.info(
            "项目创建成功 action=project.create userId=%s projectId=%s",
            owner_user_id,
            project.id,
        )
        return to_response(project)

    async def list_owned(self, owner_user_id: int) -> list[ProjectResponse]:
        logger.debug("查询项目列表 action=project.list userId=%s", owner_user_id)
        projects = await self._repository.list_by_owner(owner_user_id)
        logger.debug(
            "项目列表查询完成 action=project.list userId=%s count=%s",
            owner_user_id,
            len(projects),
        )
        return [to_response(project) for project in projects]

    async def get_owned(
        self,
        owner_user_id: int,
        project_id: int,
    ) -> ProjectResponse:
        logger.debug(
            "查询项目详情 action=project.get userId=%s projectId=%s",
            owner_user_id,
            project_id,
        )
        response = to_response(await self.require_owned(owner_user_id, project_id))
        logger.debug(
            "项目详情查询完成 action=project.get userId=%s projectId=%s",
            owner_user_id,
            project_id,
        )
        return response

    async def require_owned(self, owner_user_id: int, project_id: int) -> Project:
        project = await self._repository.get_by_id(project_id)
        if project is None or project.owner_user_id != owner_user_id:
            raise project_not_found()
        if project.status != ProjectStatus.ACTIVE.value:
            raise project_disabled()
        return project

    async def delete_owned(self, owner_user_id: int, project_id: int) -> None:
        logger.info(
            "删除项目 action=project.delete userId=%s projectId=%s",
            owner_user_id,
            project_id,
        )
        project = await self.require_owned(owner_user_id, project_id)
        prefix = self._locations.project_prefix(project.owner_user_id, project.id)
        try:
            await asyncio.to_thread(self._storage.remove_prefix, prefix)
        except AppException as exception:
            logger.exception(
                "项目对象清理失败 action=project.delete stage=storage "
                "userId=%s projectId=%s",
                owner_user_id,
                project_id,
            )
            raise AppException(ErrorCode.PROJECT_DELETE_FAILED) from exception
        try:
            await self._repository.delete(project.id)
            await self._repository.session.commit()
        except Exception as exception:
            await self._repository.session.rollback()
            logger.exception(
                "项目记录删除失败 action=project.delete stage=database "
                "userId=%s projectId=%s",
                owner_user_id,
                project_id,
            )
            raise AppException(ErrorCode.PROJECT_DELETE_FAILED) from exception
        logger.info(
            "项目删除成功 action=project.delete userId=%s projectId=%s",
            owner_user_id,
            project_id,
        )
