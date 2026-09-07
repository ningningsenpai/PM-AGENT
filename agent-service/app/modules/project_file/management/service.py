"""项目文件生命周期服务。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.core.config import FileConfig, StorageConfig
from app.core.errors import AppException, ErrorCode
from app.core.idempotency import IdempotencyGuard
from app.core.logger import get_logger
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocation,
    StorageLocationFactory,
)
from app.modules.project.service import ProjectService
from app.modules.project_file.domain import (
    FileBusinessType,
    ProjectFileStatus,
    ProjectFileUploadStatus,
)
from app.modules.project_file.management.domain import (
    prepare_metadata,
    prepare_path_metadata,
)
from app.modules.project_file.management.errors import (
    file_busy,
    file_not_found,
    file_status_invalid,
)
from app.modules.project_file.management.schemas import (
    FileReadUrlResponse,
    ProjectFileResponse,
    ProjectFileUploadResponse,
    UpdateProjectFilePathRequest,
    to_file_response,
)
from app.modules.project_file.models import ProjectFile
from app.modules.project_file.repository import ProjectFileRepository
from app.project_context.index import ProjectIndexService

logger = get_logger(__name__)


class ProjectFileService:
    MAX_UPLOAD_ATTEMPTS = 3
    ACTIVE_STATUSES = (ProjectFileStatus.ACTIVE.value,)
    OVERWRITABLE_STATUSES = (
        ProjectFileStatus.ACTIVE.value,
        ProjectFileStatus.UPLOAD_FAILED.value,
        ProjectFileStatus.VERIFY_REQUIRED.value,
    )
    DELETABLE_STATUSES = (
        ProjectFileStatus.ACTIVE.value,
        ProjectFileStatus.UPLOAD_FAILED.value,
        ProjectFileStatus.VERIFY_REQUIRED.value,
        ProjectFileStatus.DELETE_FAILED.value,
    )

    def __init__(
        self,
        repository: ProjectFileRepository,
        projects: ProjectService,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        index_service: ProjectIndexService,
        idempotency: IdempotencyGuard,
        file_config: FileConfig,
        storage_config: StorageConfig,
    ) -> None:
        self._repository = repository
        self._projects = projects
        self._storage = storage
        self._locations = locations
        self._index = index_service
        self._idempotency = idempotency
        self._file_config = file_config
        self._storage_config = storage_config

    async def upload(
        self,
        user_id: int,
        project_id: int,
        idempotency_key: str | None,
        relative_path: str,
        source_mtime_ms: int,
        content: bytes,
        supplied_content_type: str | None,
    ) -> ProjectFileUploadResponse:
        logger.info(
            "上传文件 action=project_file.upload userId=%s projectId=%s sizeBytes=%s",
            user_id,
            project_id,
            len(content),
        )
        project = await self._projects.require_owned(user_id, project_id)
        metadata = prepare_metadata(
            relative_path,
            source_mtime_ms,
            content,
            supplied_content_type,
            self._file_config,
        )
        await self._idempotency.claim(
            user_id,
            f"file:upload:{project_id}:{metadata.relative_path}",
            idempotency_key,
        )
        if await self._repository.find_path(
            project_id,
            FileBusinessType.PROJECT.value,
            metadata.path_hash,
        ):
            raise AppException(ErrorCode.FILE_PATH_CONFLICT)

        storage_uuid = self._locations.create_storage_uuid()
        location = self._locations.regular_file(
            user_id,
            project_id,
            FileBusinessType.PROJECT.value,
            metadata.file_name,
            storage_uuid,
        )
        file = ProjectFile(
            project_id=project.id,
            business_code=FileBusinessType.PROJECT.value,
            relative_path=metadata.relative_path,
            path_hash=metadata.path_hash,
            file_name=metadata.file_name,
            extension=metadata.extension,
            storage_uuid=storage_uuid,
            storage_name=self._locations.storage_name(
                metadata.file_name,
                storage_uuid,
            ),
            object_key=location.object_key,
            minio_path=self._locations.relative_object_path(
                user_id,
                project_id,
                location.object_key,
            ),
            content_type=metadata.content_type,
            size_bytes=metadata.size_bytes,
            source_mtime_ms=metadata.source_mtime_ms,
            quick_fingerprint=metadata.quick_fingerprint,
            content_hash=metadata.content_hash,
            status=ProjectFileStatus.UPLOADING.value,
            upload_status=ProjectFileUploadStatus.NOT_UPLOADED.value,
            upload_attempts=1,
            parse_attempts=0,
            lock_version=0,
        )
        try:
            await self._repository.add(file)
            await self._repository.session.commit()
            await self._repository.session.refresh(file)
        except IntegrityError as exception:
            await self._repository.session.rollback()
            logger.exception(
                "文件记录创建失败 action=project_file.upload userId=%s projectId=%s",
                user_id,
                project_id,
            )
            raise AppException(ErrorCode.FILE_PATH_CONFLICT) from exception
        logger.info(
            "文件上传记录创建成功 action=project_file.upload "
            "userId=%s projectId=%s fileId=%s",
            user_id,
            project_id,
            file.id,
        )

        try:
            await asyncio.to_thread(
                self._storage.put_bytes,
                location,
                metadata.content,
                metadata.content_type,
            )
        except AppException as exception:
            file.status = ProjectFileStatus.UPLOAD_FAILED.value
            file.upload_status = ProjectFileUploadStatus.FAILED.value
            file.last_error_code = exception.error.name
            file.last_error_message = exception.message[:500]
            file.last_failed_at = datetime.now()
            await self._repository.session.commit()
            await self._repository.session.refresh(file)
            logger.warning(
                "文件上传失败 action=project_file.upload "
                "userId=%s projectId=%s fileId=%s errorCode=%s status=%s",
                user_id,
                project_id,
                file.id,
                exception.error.name,
                file.status,
            )
            return self._upload_response(file, False, exception)

        logger.info(
            "文件对象写入成功 action=project_file.upload stage=storage "
            "userId=%s projectId=%s fileId=%s",
            user_id,
            project_id,
            file.id,
        )
        file.status = ProjectFileStatus.ACTIVE.value
        file.upload_status = ProjectFileUploadStatus.SUCCESS.value
        await self._repository.session.commit()
        await self._repository.session.refresh(file)
        logger.info(
            "文件上传成功 action=project_file.upload "
            "userId=%s projectId=%s fileId=%s status=%s",
            user_id,
            project_id,
            file.id,
            file.status,
        )
        return self._upload_response(file, True, None)

    async def overwrite(
        self,
        user_id: int,
        project_id: int,
        file_id: int,
        idempotency_key: str | None,
        source_mtime_ms: int,
        lock_version: int,
        content: bytes,
        supplied_content_type: str | None,
    ) -> ProjectFileResponse:
        logger.info(
            "覆盖文件 action=project_file.overwrite userId=%s projectId=%s fileId=%s",
            user_id,
            project_id,
            file_id,
        )
        project = await self._projects.require_owned(user_id, project_id)
        file = await self._require_public_file(project_id, file_id)
        self._require_version(file, lock_version, self.OVERWRITABLE_STATUSES)
        metadata = prepare_metadata(
            file.relative_path,
            source_mtime_ms,
            content,
            supplied_content_type,
            self._file_config,
        )
        await self._idempotency.claim(
            user_id,
            f"file:content:{project_id}:{file_id}",
            idempotency_key,
        )
        content_changed = file.content_hash != metadata.content_hash
        upload_required = (
            content_changed
            or file.upload_status != ProjectFileUploadStatus.SUCCESS.value
        )
        await self._claim_state(
            file,
            lock_version,
            ProjectFileStatus.UPDATING,
            self.OVERWRITABLE_STATUSES,
        )

        if not upload_required:
            self._apply_content_metadata(file, metadata)
            file.status = ProjectFileStatus.ACTIVE.value
            await self._repository.session.commit()
            await self._repository.session.refresh(file)
            await self._rebuild_index(project)
            logger.info(
                "文件内容未变化 action=project_file.overwrite "
                "userId=%s projectId=%s fileId=%s",
                user_id,
                project_id,
                file_id,
            )
            return to_file_response(file)

        file.upload_status = ProjectFileUploadStatus.RETRYING.value
        await self._repository.session.commit()

        location = self._location_of(file)
        last_exception: AppException | None = None
        for attempt in range(1, self.MAX_UPLOAD_ATTEMPTS + 1):
            try:
                await asyncio.to_thread(
                    self._storage.put_bytes,
                    location,
                    metadata.content,
                    metadata.content_type,
                )
            except AppException as exception:
                last_exception = exception
                file.upload_attempts += 1
                file.status = (
                    ProjectFileStatus.VERIFY_REQUIRED.value
                    if attempt < self.MAX_UPLOAD_ATTEMPTS
                    else ProjectFileStatus.UPLOAD_FAILED.value
                )
                file.upload_status = (
                    ProjectFileUploadStatus.RETRYING.value
                    if attempt < self.MAX_UPLOAD_ATTEMPTS
                    else ProjectFileUploadStatus.FAILED.value
                )
                file.last_error_code = exception.error.name
                file.last_error_message = exception.message[:500]
                file.last_failed_at = datetime.now()
                await self._repository.session.commit()
                logger.warning(
                    "文件覆盖重试失败 action=project_file.overwrite "
                    "userId=%s projectId=%s fileId=%s "
                    "attempt=%s errorCode=%s status=%s",
                    user_id,
                    project_id,
                    file_id,
                    attempt,
                    exception.error.name,
                    file.status,
                )
                if attempt < self.MAX_UPLOAD_ATTEMPTS:
                    file.status = ProjectFileStatus.UPDATING.value
                    await self._repository.session.commit()
                continue

            stale_detail_ref = None
            self._apply_content_metadata(file, metadata)
            if content_changed:
                stale_detail_ref = self._invalidate_analysis(file)
            file.status = ProjectFileStatus.ACTIVE.value
            file.upload_status = ProjectFileUploadStatus.SUCCESS.value
            file.upload_attempts += 1
            file.last_error_code = None
            file.last_error_message = None
            file.last_failed_at = None
            await self._repository.session.commit()
            await self._repository.session.refresh(file)
            await self._remove_invalidated_detail(
                project,
                file.id,
                stale_detail_ref,
            )
            await self._rebuild_index(project)
            logger.info(
                "文件覆盖成功 action=project_file.overwrite "
                "userId=%s projectId=%s fileId=%s attempts=%s",
                user_id,
                project_id,
                file_id,
                attempt,
            )
            return to_file_response(file)

        await self._rebuild_index(project)
        logger.warning(
            "文件覆盖重试耗尽 action=project_file.overwrite "
            "userId=%s projectId=%s fileId=%s attempts=%s",
            user_id,
            project_id,
            file_id,
            self.MAX_UPLOAD_ATTEMPTS,
        )
        raise AppException(
            ErrorCode.FILE_UPLOAD_RETRY_EXHAUSTED,
            last_exception.message if last_exception else None,
        )

    async def update_path(
        self,
        user_id: int,
        project_id: int,
        file_id: int,
        request: UpdateProjectFilePathRequest,
    ) -> ProjectFileResponse:
        logger.info(
            "修改文件路径 action=project_file.path.update "
            "userId=%s projectId=%s fileId=%s",
            user_id,
            project_id,
            file_id,
        )
        project = await self._projects.require_owned(user_id, project_id)
        file = await self._require_public_file(project_id, file_id)
        self._require_version(file, request.lock_version, self.ACTIVE_STATUSES)
        metadata = prepare_path_metadata(
            request.relative_path,
            request.source_mtime_ms,
            self._file_config,
        )
        path_changed = metadata.path_hash != file.path_hash
        existing = await self._repository.find_path(
            project_id,
            file.business_code,
            metadata.path_hash,
        )
        if existing is not None and existing.id != file.id:
            raise AppException(ErrorCode.FILE_PATH_CONFLICT)
        await self._claim_state(
            file,
            request.lock_version,
            ProjectFileStatus.UPDATING,
            self.ACTIVE_STATUSES,
        )

        old_location = self._location_of(file)
        if metadata.file_name == file.file_name:
            self._apply_path_metadata(file, metadata)
            stale_detail_ref = self._invalidate_analysis(file) if path_changed else None
            file.status = ProjectFileStatus.ACTIVE.value
            await self._repository.session.commit()
            await self._repository.session.refresh(file)
            await self._remove_invalidated_detail(
                project,
                file.id,
                stale_detail_ref,
            )
            await self._rebuild_index(project)
            logger.info(
                "文件路径修改成功 action=project_file.path.update "
                "mode=metadata userId=%s projectId=%s fileId=%s",
                user_id,
                project_id,
                file_id,
            )
            return to_file_response(file)

        target = self._locations.regular_file(
            user_id,
            project_id,
            file.business_code,
            metadata.file_name,
            file.storage_uuid,
        )
        try:
            await asyncio.to_thread(self._storage.copy, old_location, target)
        except AppException as exception:
            file.status = ProjectFileStatus.ACTIVE.value
            await self._repository.session.commit()
            logger.exception(
                "文件对象复制失败 action=project_file.path.update "
                "stage=copy userId=%s projectId=%s fileId=%s",
                user_id,
                project_id,
                file_id,
            )
            raise AppException(ErrorCode.FILE_RENAME_FAILED) from exception

        self._apply_path_metadata(file, metadata)
        stale_detail_ref = self._invalidate_analysis(file)
        file.storage_name = self._locations.storage_name(
            metadata.file_name,
            file.storage_uuid,
        )
        file.object_key = target.object_key
        file.minio_path = self._locations.relative_object_path(
            user_id,
            project_id,
            target.object_key,
        )
        file.status = ProjectFileStatus.ACTIVE.value
        await self._repository.session.commit()
        await self._repository.session.refresh(file)
        await self._remove_invalidated_detail(
            project,
            file.id,
            stale_detail_ref,
        )
        try:
            await asyncio.to_thread(self._storage.remove, old_location)
        except AppException as exception:
            file.status = ProjectFileStatus.VERIFY_REQUIRED.value
            await self._repository.session.commit()
            await self._rebuild_index(project)
            logger.exception(
                "旧文件对象删除失败 action=project_file.path.update "
                "stage=remove_old userId=%s projectId=%s fileId=%s",
                user_id,
                project_id,
                file_id,
            )
            raise AppException(ErrorCode.FILE_RENAME_FAILED) from exception

        await self._rebuild_index(project)
        logger.info(
            "文件路径修改成功 action=project_file.path.update "
            "mode=storage userId=%s projectId=%s fileId=%s",
            user_id,
            project_id,
            file_id,
        )
        return to_file_response(file)

    async def list_files(
        self,
        user_id: int,
        project_id: int,
        business_code: str | None,
    ) -> list[ProjectFileResponse]:
        logger.debug(
            "查询文件列表 action=project_file.list userId=%s projectId=%s business=%s",
            user_id,
            project_id,
            business_code,
        )
        await self._projects.require_owned(user_id, project_id)
        if business_code == FileBusinessType.SYSTEM.value:
            raise AppException(ErrorCode.SYSTEM_FILE_ACCESS_DENIED)
        if business_code and business_code not in {
            FileBusinessType.PROJECT.value,
            FileBusinessType.USER.value,
        }:
            raise AppException(ErrorCode.PARAM_INVALID, "文件业务类型不合法")
        files = await self._repository.list(project_id, business_code)
        logger.debug(
            "文件列表查询完成 action=project_file.list userId=%s projectId=%s count=%s",
            user_id,
            project_id,
            len(files),
        )
        result = [to_file_response(file) for file in files]
        await self._repository.session.commit()
        return result

    async def read_evidence(
        self,
        user_id: int,
        project_id: int,
        file_id: int,
        start_line: int = 1,
        end_line: int = 200,
    ) -> dict:
        """读取当前项目源文件的脱敏证据；行号来自真实提取文本。"""
        import hashlib

        from app.project_context.file_detail import FileDownloader
        from app.project_context.file_detail.extraction import (
            FileContentExtractionService,
            FileContentExtractorFactory,
        )
        from app.project_context.file_detail.sensitive_content import (
            sanitize_sensitive_content,
        )

        if start_line < 1 or end_line < start_line or end_line - start_line >= 200:
            raise AppException(
                ErrorCode.PARAM_INVALID, "证据行范围必须连续且不超过 200 行"
            )
        await self._projects.require_owned(user_id, project_id)
        file = await self._require_public_file(project_id, file_id)
        if file.status != "active" or file.upload_status != "success":
            raise file_status_invalid()
        location = self._locations.existing_object(user_id, project_id, file.object_key)
        filename, content_type, expected_hash, path = (
            file.file_name,
            file.content_type,
            file.content_hash,
            file.relative_path,
        )
        await self._repository.session.commit()
        raw = await asyncio.to_thread(self._storage.read_bytes, location)
        if hashlib.sha256(raw).hexdigest() != expected_hash:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "源文件哈希与当前记录不一致，请刷新后重试"
            )
        extraction = FileContentExtractionService(
            FileDownloader(), FileContentExtractorFactory()
        )
        extracted = await extraction.extract_from_bytes(raw, content_type, filename)
        sanitized = sanitize_sensitive_content(extracted.get("text", ""))
        lines = sanitized.text.splitlines()
        if start_line > max(1, len(lines)):
            raise AppException(ErrorCode.PARAM_INVALID, "起始行超出实际文件范围")
        actual_end, rendered, used, truncated = start_line - 1, [], 0, False
        for line_no in range(start_line, min(end_line, len(lines)) + 1):
            item = f"{line_no}: {lines[line_no - 1]}"
            encoded = (item + "\n").encode("utf-8")
            if used + len(encoded) > 32768:
                if not rendered:
                    rendered.append(encoded[:32767].decode("utf-8", errors="ignore"))
                    actual_end = line_no
                truncated = True
                break
            used += len(encoded)
            rendered.append(item)
            actual_end = line_no
        return {
            "fileId": file_id,
            "logicalPath": path,
            "contentHash": expected_hash,
            "startLine": start_line,
            "endLine": actual_end,
            "totalLines": len(lines),
            "text": "\n".join(rendered),
            "truncated": truncated,
            "hasMore": actual_end < len(lines),
            "redacted": bool(sanitized.flags),
        }

    async def create_read_url(
        self,
        user_id: int,
        project_id: int,
        file_id: int,
    ) -> FileReadUrlResponse:
        await self._projects.require_owned(user_id, project_id)
        file = await self._require_public_file(project_id, file_id)
        if file.status != ProjectFileStatus.ACTIVE.value:
            raise file_status_invalid()
        url = await asyncio.to_thread(
            self._storage.presigned_get,
            self._location_of(file),
        )
        logger.info(
            "文件读取地址签发成功 action=project_file.read_url "
            "userId=%s projectId=%s fileId=%s expiresIn=%s",
            user_id,
            project_id,
            file_id,
            self._storage_config.read_url_expiry_seconds,
        )
        return FileReadUrlResponse(
            file_id=file.id,
            file_name=file.file_name,
            url=url,
            expires_at=datetime.now()
            + timedelta(seconds=self._storage_config.read_url_expiry_seconds),
        )

    async def delete(
        self,
        user_id: int,
        project_id: int,
        file_id: int,
        lock_version: int,
    ) -> None:
        logger.info(
            "删除文件 action=project_file.delete userId=%s projectId=%s fileId=%s",
            user_id,
            project_id,
            file_id,
        )
        project = await self._projects.require_owned(user_id, project_id)
        file = await self._require_public_file(project_id, file_id)
        self._require_version(file, lock_version, self.DELETABLE_STATUSES)
        detail_location = (
            self._locations.system_file(
                project.owner_user_id,
                project.id,
                file.detail_ref.removeprefix("system/"),
            )
            if file.detail_ref
            else None
        )
        await self._claim_state(
            file,
            lock_version,
            ProjectFileStatus.DELETING,
            self.DELETABLE_STATUSES,
        )
        try:
            await asyncio.to_thread(self._storage.remove, self._location_of(file))
            await self._repository.delete(file.id)
            await self._repository.session.commit()
        except Exception:
            logger.exception(
                "文件删除失败 action=project_file.delete "
                "userId=%s projectId=%s fileId=%s",
                user_id,
                project_id,
                file_id,
            )
            await self._repository.session.rollback()
            current = await self._repository.get(project_id, file_id)
            if current is not None:
                current.status = ProjectFileStatus.DELETE_FAILED.value
                await self._repository.session.commit()
            raise
        if detail_location is not None:
            try:
                await asyncio.to_thread(self._storage.remove, detail_location)
            except AppException:
                logger.warning(
                    "文件详情清理失败 action=project_file.delete.detail "
                    "userId=%s projectId=%s fileId=%s",
                    user_id,
                    project_id,
                    file_id,
                )
        await self._rebuild_index(project)
        logger.info(
            "文件删除成功 action=project_file.delete userId=%s projectId=%s fileId=%s",
            user_id,
            project_id,
            file_id,
        )

    async def _require_public_file(
        self,
        project_id: int,
        file_id: int,
    ) -> ProjectFile:
        file = await self._repository.get(project_id, file_id)
        if file is None:
            raise file_not_found()
        if file.business_code == FileBusinessType.SYSTEM.value:
            raise AppException(ErrorCode.SYSTEM_FILE_ACCESS_DENIED)
        return file

    @staticmethod
    def _require_version(
        file: ProjectFile,
        lock_version: int,
        allowed_statuses: tuple[str, ...],
    ) -> None:
        if file.status not in allowed_statuses:
            raise file_status_invalid()
        if file.lock_version != lock_version:
            raise file_busy()

    async def _claim_state(
        self,
        file: ProjectFile,
        expected_lock_version: int,
        status: ProjectFileStatus,
        expected_statuses: tuple[str, ...],
    ) -> None:
        claimed = await self._repository.claim_state(
            file.project_id,
            file.id,
            expected_lock_version,
            expected_statuses,
            status.value,
        )
        if not claimed:
            await self._repository.session.rollback()
            raise file_busy()
        await self._repository.session.commit()
        await self._repository.session.refresh(file)
        logger.debug(
            "文件状态声明成功 action=project_file.state.claim "
            "projectId=%s fileId=%s status=%s lockVersion=%s",
            file.project_id,
            file.id,
            status.value,
            expected_lock_version,
        )

    @staticmethod
    def _apply_content_metadata(file: ProjectFile, metadata) -> None:
        file.content_type = metadata.content_type
        file.size_bytes = metadata.size_bytes
        file.source_mtime_ms = metadata.source_mtime_ms
        file.quick_fingerprint = metadata.quick_fingerprint
        file.content_hash = metadata.content_hash

    @staticmethod
    def _invalidate_analysis(file: ProjectFile) -> str | None:
        """清除当前详情引用，使变化后的文件重新进入分析候选。"""
        stale_detail_ref = file.detail_ref
        file.parse_attempts = 0
        file.detail_ref = None
        file.module = None
        file.kind = None
        file.file_type = None
        file.language = None
        file.importance = None
        file.summary = None
        file.keywords = None
        file.last_error_code = None
        file.last_error_message = None
        file.last_failed_at = None
        return stale_detail_ref

    async def _remove_invalidated_detail(
        self,
        project,
        file_id: int,
        detail_ref: str | None,
    ) -> None:
        """数据库解除引用后尽力清理旧详情，清理失败不回滚文件变更。"""
        if detail_ref is None:
            return
        location = self._locations.system_file(
            project.owner_user_id,
            project.id,
            detail_ref.removeprefix("system/"),
        )
        try:
            await asyncio.to_thread(self._storage.remove, location)
        except AppException:
            logger.warning(
                "失效文件详情清理失败 action=project_file.detail.cleanup "
                "projectId=%s fileId=%s",
                project.id,
                file_id,
            )

    @staticmethod
    def _apply_path_metadata(file: ProjectFile, metadata) -> None:
        file.relative_path = metadata.relative_path
        file.path_hash = metadata.path_hash
        file.file_name = metadata.file_name
        file.extension = metadata.extension
        file.source_mtime_ms = metadata.source_mtime_ms
        raw = (
            f"{metadata.relative_path}\0{file.size_bytes}\0{metadata.source_mtime_ms}"
        ).encode()
        from hashlib import sha256

        file.quick_fingerprint = sha256(raw).hexdigest()

    def _location_of(self, file: ProjectFile) -> StorageLocation:
        return StorageLocation(self._storage_config.bucket, file.object_key)

    async def _rebuild_index(self, project) -> None:
        logger.debug(
            "重建项目文件索引 action=project_file.index.rebuild projectId=%s",
            project.id,
        )
        files = await self._repository.list(
            project.id,
            include_system=True,
        )
        await self._repository.session.commit()
        await self._index.write(project, files)
        logger.debug(
            "项目文件索引重建完成 action=project_file.index.rebuild "
            "projectId=%s count=%s",
            project.id,
            len(files),
        )

    @staticmethod
    def _upload_response(
        file: ProjectFile,
        succeeded: bool,
        exception: AppException | None,
    ) -> ProjectFileUploadResponse:
        return ProjectFileUploadResponse(
            file_id=file.id,
            relative_path=file.relative_path,
            file_name=file.file_name,
            success=succeeded,
            status=file.status,
            upload_status=file.upload_status,
            error_code=exception.error.name if exception else None,
            error_message=exception.message if exception else None,
        )
