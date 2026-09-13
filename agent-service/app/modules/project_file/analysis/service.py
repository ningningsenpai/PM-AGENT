"""项目文件分析与上下文发布编排服务。"""

from __future__ import annotations

import asyncio
import hashlib
import json

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.core.trace import get_trace_id
from app.infrastructure.storage import (
    ObjectStorage,
    StorageLocationFactory,
)
from app.llm.telemetry import capture_calls
from app.modules.chat.runs.service import RunService
from app.modules.chat.context.fixed_store import FixedContextStore, LONG_MEMORY
from app.modules.chat.context.migration import stable_id
from app.modules.chat.context.schemas import EntryView
from app.modules.project.service import ProjectService
from app.modules.project_file.analysis.schemas import (
    ProjectFileAnalysisBatchResult,
    ProjectFileAnalysisFailure,
)
from app.modules.project_file.models import ProjectFile
from app.modules.project_file.repository import ProjectFileRepository
from app.project_context.file_detail.extraction import (
    FileContentExtractionService,
)
from app.project_context.file_detail.schemas import (
    FileSemanticAnalysisRequest,
    FileSemanticAnalysisResult,
    FileDetail,
)
from app.project_context.file_detail.service import FileSemanticAnalysisService
from app.project_context.index import ProjectIndexService
from app.project_context.specification import ProjectSpecificationService

logger = get_logger(__name__)


class ProjectFileAnalysisService:
    """编排源文件读取、内容提取、语义分析、详情发布和上下文刷新。"""

    def __init__(
        self,
        repository: ProjectFileRepository,
        projects: ProjectService,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        index_service: ProjectIndexService,
        content_extractor: FileContentExtractionService,
        semantic_analyzer: FileSemanticAnalysisService,
        specification_service: ProjectSpecificationService,
        runs: RunService,
    ) -> None:
        self._repository = repository
        self._projects = projects
        self._storage = storage
        self._locations = locations
        self._index = index_service
        self._content_extractor = content_extractor
        self._semantic_analyzer = semantic_analyzer
        self._specification = specification_service
        self._runs = runs

    async def analyze_pending_files(
        self,
        user_id: int,
        project_id: int,
        idempotency_key: str | None,
        *,
        force: bool = False,
        file_ids: list[int] | None = None,
    ) -> ProjectFileAnalysisBatchResult:
        """
        处理前端传递的信息进行后续的文件解析处理
        默认解析 -> force = False, file_ids = []，即全权交给后端根据 MySQL 整理数据然后进行解析。
        前端重试 -> force = True, file_ids != []，由前端选择对应的文件进行解析重试
        """
        normalized_file_ids = sorted(set(file_ids)) if file_ids is not None else None
        run, fresh = await self._runs.start(
            user_id,
            project_id,
            "parse",
            idempotency_key,
            {"force": force, "fileIds": normalized_file_ids},
            get_trace_id(),
            exclusive_scope=f"project-file-parse:{project_id}",
        )
        if not fresh:
            if run.result:
                return ProjectFileAnalysisBatchResult.model_validate(run.result)
            if run.status == "running":
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT,
                    f"相同文件解析请求仍在执行，运行编号：{run.id}",
                )
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT,
                "此前文件解析请求未成功完成，请使用新的幂等键重新发起",
            )
        run_id, events = run.id, []
        try:
            async with self._runs.keep_alive(run_id, user_id):
                with capture_calls(events):
                    result = await self._analyze_pending_files(
                        user_id,
                        project_id,
                        run_id=run_id,
                        force=force,
                        file_ids=normalized_file_ids,
                    )
            result = result.model_copy(update={"run_id": str(run_id)})
            await self._runs.finish(
                run_id,
                user_id,
                events,
                result.model_dump(mode="json", by_alias=True),
                error="本批存在未成功解析或发布的项目，请查看结果明细"
                if result.status != "success"
                else None,
            )
            return result
        except asyncio.CancelledError:
            await self._runs.cancel(run_id, user_id, events)
            raise
        except Exception as exc:
            logger.exception("文件批次运行中断，保留模型轨迹")
            await self._repository.session.rollback()
            await self._runs.finish(
                run_id, user_id, events, error=f"解析运行失败：{type(exc).__name__}"
            )
            raise

    async def recover(self, user_id, project_id, idempotency_key):
        """查询原解析请求的确定状态，不触发模型调用。"""
        return await self._runs.recover(user_id, project_id, "parse", idempotency_key)

    async def _analyze_pending_files(
        self, user_id, project_id, *, run_id, force=False, file_ids=None
    ):
        project = await self._projects.require_owned(user_id, project_id)
        options = {"file_ids": file_ids} if file_ids is not None else {}
        if file_ids is not None:
            for file_id in file_ids:
                selected = await self._repository.get(project_id, file_id)
                if selected is None or selected.business_code == "system":
                    raise AppException(ErrorCode.FILE_NOT_FOUND)
        candidates = await self._repository.list_analysis_candidates(
            project_id,
            force=force,
            **options,
        )
        await self._repository.session.commit()
        await self._runs.renew(run_id, user_id)
        logger.info(
            "开始分析项目文件 action=project_file.analysis.batch "
            "userId=%s projectId=%s force=%s candidateCount=%s",
            user_id,
            project_id,
            force,
            len(candidates),
        )

        success_count = 0
        failure_count = 0
        successful_file_ids: set[int] = set()
        successful_details: list[FileDetail] = []
        failures: list[ProjectFileAnalysisFailure] = []
        for file in candidates:
            await self._runs.renew(run_id, user_id)
            request = self._build_request(project.owner_user_id, file)
            result = await self._analyze_file(file, request)
            if result.status == "success" and result.detail is not None:
                await self._runs.ensure_active(run_id, user_id)
                result = await self._write_detail_or_failure(
                    project.owner_user_id,
                    project.id,
                    result,
                )
            # 确保详情文件上传成功之后才可以修改 MySQL
            await self._runs.ensure_active(run_id, user_id)
            if result.status == "success" and result.detail is not None:
                updated = await self._repository.record_analysis_success(
                    project_id,
                    file.id,
                    file.content_hash,
                    file.lock_version,
                    result.detail,
                    promote_constraint_source=(
                        result.detail.may_supply_project_constraints
                        and not file.may_supply_constraints
                    ),
                )
            else:
                updated = await self._repository.record_analysis_failure(
                    project_id,
                    file.id,
                    file.content_hash,
                    file.lock_version,
                    result.error_code or "FILE_DETAIL_ANALYSIS_FAILED",
                    result.error_message or "文件分析失败",
                )
            if not updated:
                await self._repository.session.rollback()
                logger.error(
                    "文件分析结果落库冲突 action=project_file.analysis.batch "
                    "userId=%s projectId=%s fileId=%s",
                    user_id,
                    project_id,
                    file.id,
                )
                raise AppException(
                    ErrorCode.SYSTEM_ERROR,
                    "文件分析结果落库失败，文件可能已发生变化",
                )
            await self._repository.session.commit()
            if result.status == "success":
                success_count += 1
                successful_file_ids.add(file.id)
                if result.detail is not None:
                    successful_details.append(result.detail)
                logger.info(
                    "文件语义分析成功 action=project_file.semantic.analyze "
                    "userId=%s projectId=%s fileId=%s",
                    user_id,
                    project_id,
                    file.id,
                )
            else:
                failure_count += 1
                failures.append(
                    ProjectFileAnalysisFailure(
                        file_id=file.id,
                        relative_path=file.relative_path,
                        error_code=(result.error_code or "FILE_DETAIL_ANALYSIS_FAILED"),
                        error_message=result.error_message or "文件分析失败",
                    )
                )
                logger.warning(
                    "文件分析失败 action=project_file.analysis.batch "
                    "userId=%s projectId=%s fileId=%s errorCode=%s",
                    user_id,
                    project_id,
                    file.id,
                    result.error_code or "FILE_DETAIL_ANALYSIS_FAILED",
                )

        files = await self._repository.list(project_id, include_system=True)
        await self._repository.session.commit()
        await self._runs.renew(run_id, user_id)
        specification_status = "updated"
        await self._runs.ensure_active(run_id, user_id)
        try:
            specification_status = await self._specification.refresh(
                project,
                files,
                [file for file in files if file.id in successful_file_ids],
            )
        except Exception:
            specification_status = "failed"
            logger.exception(
                "项目规范刷新失败，保留原有规范 "
                "action=project_file.analysis.batch "
                "userId=%s projectId=%s",
                user_id,
                project_id,
            )
        memory_status = "kept"
        try:
            memory_status = await self._refresh_long_term_memory(
                project, successful_details
            )
        except Exception:
            memory_status = "failed"
            logger.exception(
                "长期记忆刷新失败，保留原文件 action=project_file.memory.refresh "
                "userId=%s projectId=%s",
                user_id,
                project_id,
            )
        index_status = "updated"
        await self._runs.ensure_active(run_id, user_id)
        try:
            await self._index.write(project, files)
        except Exception:
            index_status = "failed"
            logger.exception(
                "项目索引发布失败 action=project_file.analysis.batch "
                "userId=%s projectId=%s",
                user_id,
                project_id,
            )
        status = (
            "partial"
            if failure_count
            or specification_status == "failed"
            or index_status == "failed"
            or memory_status == "failed"
            else "success"
        )
        logger.info(
            "项目文件分析完成 action=project_file.analysis.batch "
            "userId=%s projectId=%s successCount=%s failureCount=%s",
            user_id,
            project_id,
            success_count,
            failure_count,
        )
        return ProjectFileAnalysisBatchResult(
            status=status,
            candidate_count=len(candidates),
            success_count=success_count,
            failure_count=failure_count,
            failures=failures,
            specification_status=specification_status,
            index_status=index_status,
            memory_status=memory_status,
        )

    async def _refresh_long_term_memory(
        self,
        project,
        details: list[FileDetail],
    ) -> str:
        """只替换本轮成功文件提供的项目事实，保留对话形成的长期记忆。"""
        if not details:
            return "kept"
        location = self._locations.system_file(
            project.owner_user_id, project.id, LONG_MEMORY
        )
        store = FixedContextStore(self._storage, location.bucket)
        document, etag = await store.read(
            project.owner_user_id, project.id, LONG_MEMORY
        )
        current = store.document_entries(
            project.owner_user_id, project.id, LONG_MEMORY, document
        )
        by_file: dict[int, list[dict]] = {}
        for entry in current:
            file_id = entry.get("attributes", {}).get("sourceFileId")
            if file_id is not None:
                by_file.setdefault(int(file_id), []).append(entry)

        changes: list[dict] = []
        for detail in details:
            old_entries = by_file.get(detail.file_id, [])
            old_by_id = {entry["id"]: entry for entry in old_entries}
            desired = self._memory_entries(project.id, detail, old_by_id)
            desired_by_id = {entry["id"]: entry for entry in desired}
            for entry_id in old_by_id.keys() - desired_by_id.keys():
                changes.append(
                    {
                        "entryId": entry_id,
                        "delete": True,
                        "reason": "来源文件重新分析后不再包含该项目事实",
                        "version": old_by_id[entry_id]["version"] + 1,
                    }
                )
            for entry_id, entry in desired_by_id.items():
                before = old_by_id.get(entry_id)
                if before is not None and self._same_memory_entry(before, entry):
                    continue
                changes.append(
                    {
                        "entryId": entry_id,
                        "before": before or {},
                        "after": entry,
                        "version": entry["version"],
                        "reason": "项目文件语义分析同步长期记忆",
                    }
                )
        if not changes:
            return "kept"
        await store.apply(
            project.owner_user_id,
            project.id,
            LONG_MEMORY,
            changes,
            etag,
        )
        return "updated"

    @staticmethod
    def _memory_entries(project_id: int, detail: FileDetail, old_by_id: dict) -> list[dict]:
        entries: list[dict] = []
        for fact in detail.project_facts:
            statement = str(fact.get("statement") or "").strip()
            quote = str(fact.get("source_quote") or "").strip()
            if not statement or not quote or fact.get("evidence_verified") is not True:
                continue
            kind = str(fact.get("kind") or "project_observation")[:64]
            entry_id = stable_id(
                f"project-fact:{project_id}:{detail.file_id}:{kind}:{statement}"
            )
            previous = old_by_id.get(entry_id)
            entry = EntryView(
                id=entry_id,
                project_id=project_id,
                kind="long_memory",
                content=statement,
                attributes={
                    "key": f"project_fact.{kind}.{hashlib.sha256(statement.encode()).hexdigest()[:16]}",
                    "sourceType": "file_detail",
                    "sourceFileId": detail.file_id,
                    "sourcePath": detail.original_path,
                    "contentHash": detail.content_hash,
                    "detailRef": detail.detail_ref,
                    "factKind": kind,
                    "state": ProjectFileAnalysisService._fact_state(kind),
                    "sourceQuote": quote,
                    "sourceRange": fact.get("source_range") or {},
                },
                status="active",
                version=(previous or {}).get("version", 0) + 1,
                source_message_id=None,
                expires_at=None,
            ).model_dump(mode="json", by_alias=True)
            entries.append(entry)
        return entries

    @staticmethod
    def _same_memory_entry(before: dict, after: dict) -> bool:
        return all(
            before.get(field) == after.get(field)
            for field in ("content", "status", "conditions", "expiresAt", "attributes")
        )

    @staticmethod
    def _fact_state(kind: str) -> str:
        normalized = kind.lower()
        if any(word in normalized for word in ("completed", "done", "finished")):
            return "observed_complete"
        if any(word in normalized for word in ("progress", "in_progress", "developing")):
            return "in_progress"
        if any(word in normalized for word in ("planned", "todo", "expected")):
            return "planned"
        return "observed"

    async def _analyze_file(
        self,
        file: ProjectFile,
        request: FileSemanticAnalysisRequest,
    ) -> FileSemanticAnalysisResult:
        """读取指定文件快照，提取标准文本并执行语义分析。"""
        try:
            source_bytes = await asyncio.to_thread(
                self._storage.read_bytes,
                self._locations.existing_object(
                    request.user_id,
                    file.project_id,
                    file.object_key,
                ),
            )
        except AppException as exception:
            logger.warning(
                "源文件读取失败 action=project_file.source.read "
                "projectId=%s fileId=%s errorCode=%s",
                file.project_id,
                file.id,
                exception.error.name,
            )
            return FileSemanticAnalysisResult(
                project_id=file.project_id,
                file_id=file.id,
                content_hash=file.content_hash,
                status="failed",
                error_code=exception.error.name,
                error_message=exception.message,
            )
        try:
            extracted_content = await self._content_extractor.extract_from_bytes(
                source_bytes,
                request.file_type,
                request.filename,
            )
        except Exception:
            logger.exception(
                "文件内容提取失败 action=project_file.content.extract "
                "projectId=%s fileId=%s",
                file.project_id,
                file.id,
            )
            return FileSemanticAnalysisResult(
                project_id=file.project_id,
                file_id=file.id,
                content_hash=file.content_hash,
                status="failed",
                error_code="FILE_DETAIL_ANALYSIS_FAILED",
                error_message="文件内容提取失败",
            )
        try:
            return await self._semantic_analyzer.analyze(request, extracted_content)
        except Exception:
            logger.exception(
                "文件语义分析器执行失败 action=project_file.semantic.analyze "
                "projectId=%s fileId=%s",
                file.project_id,
                file.id,
            )
            return FileSemanticAnalysisResult(
                project_id=file.project_id,
                file_id=file.id,
                content_hash=file.content_hash,
                status="failed",
                error_code="FILE_DETAIL_ANALYSIS_FAILED",
                error_message="文件语义分析器执行失败",
            )

    async def _write_detail(
        self,
        user_id: int,
        project_id: int,
        result: FileSemanticAnalysisResult,
    ) -> None:
        """将服务端组装的文件详情写入 system 区域。"""
        detail = result.detail
        if detail is None:
            raise AppException(ErrorCode.FILE_ANALYSIS_FAILED)
        location = self._locations.system_file(
            user_id,
            project_id,
            detail.detail_ref.removeprefix("system/"),
        )
        await asyncio.to_thread(
            self._storage.put_bytes,
            location,
            json.dumps(
                detail.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
            "application/json",
        )
        logger.debug(
            "文件详情写入完成 action=project_file.detail.write projectId=%s fileId=%s",
            project_id,
            result.file_id,
        )

    async def _write_detail_or_failure(
        self,
        user_id: int,
        project_id: int,
        result: FileSemanticAnalysisResult,
    ) -> FileSemanticAnalysisResult:
        """将解析之后的详情文件上传云端或者组合失败信息"""
        try:
            await self._write_detail(user_id, project_id, result)
            return result
        except AppException as exception:
            error_code = exception.error.name
            error_message = exception.message
            logger.warning(
                "文件详情写入失败 action=project_file.detail.write "
                "projectId=%s fileId=%s errorCode=%s",
                project_id,
                result.file_id,
                error_code,
            )
        except Exception:
            error_code = "FILE_DETAIL_WRITE_FAILED"
            error_message = "文件详情写入失败"
            logger.exception(
                "文件详情写入失败 action=project_file.detail.write "
                "projectId=%s fileId=%s errorCode=%s",
                project_id,
                result.file_id,
                error_code,
            )
        return FileSemanticAnalysisResult(
            project_id=result.project_id,
            file_id=result.file_id,
            content_hash=result.content_hash,
            status="failed",
            error_code=error_code,
            error_message=error_message,
        )

    def _build_request(
        self,
        user_id: int,
        file: ProjectFile,
    ) -> FileSemanticAnalysisRequest:
        """构建包含当前文件快照身份的分析请求。"""
        detail_ref = (
            f"system/file_details/{file.storage_uuid}-"
            f"{file.content_hash}-{file.path_hash}.json"
        )
        return FileSemanticAnalysisRequest(
            user_id=user_id,
            project_id=file.project_id,
            business=file.business_code,
            file_id=file.id,
            filename=file.file_name,
            file_url="",
            file_type=file.extension or file.content_type,
            storage_uuid=file.storage_uuid,
            storage_name=file.storage_name,
            detail_ref=detail_ref,
            original_path=file.relative_path,
            minio_path=file.minio_path,
            size_bytes=file.size_bytes,
            content_type=file.content_type,
            content_hash=file.content_hash,
        )
