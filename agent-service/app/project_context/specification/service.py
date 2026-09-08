"""项目规范生成与对象存储服务。"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import ValidationError

from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.infrastructure.storage import ObjectStorage, StorageLocationFactory
from app.llm.prompts.project_context import ProjectSpecificationPrompt
from app.llm.structured import StructuredJsonGenerator, StructuredOutputTruncatedError
from app.project_context.file_detail.schemas import FileDetail
from app.project_context.file_detail.sensitive_content import (
    SensitiveContentBlockedError,
    sanitize_sensitive_content,
)
from app.project_context.specification.model_output import normalize_specification_json
from app.project_context.specification.schemas import (
    ProjectSpecificationDocument,
    SpecificationSourceRef,
    merge_specifications,
)

logger = get_logger(__name__)

SpecificationRefreshStatus = Literal["updated", "kept"]


class ProjectSpecificationService:
    """分批聚合全部有效详情规则候选，合并完成后发布项目规范。"""

    _MAX_BATCH_CANDIDATES = 12
    _MAX_BATCH_SOURCE_CHARS = 12000

    _RULE_FIELDS = (
        "development_approach",
        "technical_constraints",
        "coding_rules",
        "document_rules",
        "risk_rules",
    )

    def __init__(
        self,
        storage: ObjectStorage,
        locations: StorageLocationFactory,
        generator: StructuredJsonGenerator | None = None,
    ) -> None:
        self._storage = storage
        self._locations = locations
        self._generator = generator

    async def initialize(self, project) -> SpecificationRefreshStatus:
        """不调用模型，为新项目写入合法空规范。"""
        location = self._location(project)
        existing = await self._load_existing(location, project.id)
        if existing is not None:
            return "kept"
        await self._write(location, ProjectSpecificationDocument.empty(project.id))
        return "updated"

    async def refresh(
        self,
        project,
        files: Iterable[Any],
    ) -> SpecificationRefreshStatus:
        current_files = list(files)
        location = self._location(project)
        existing = await self._load_existing(location, project.id)
        inventory = self._build_inventory(current_files)
        sources = await self._load_rule_sources(project, current_files)
        stale_rule_keys = self._stale_rule_keys(existing, inventory)
        if not sources and not stale_rule_keys:
            if existing is None:
                await self._write(
                    location, ProjectSpecificationDocument.empty(project.id)
                )
                return "updated"
            return "kept"
        if self._generator is None:
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED)

        try:
            generated = await self._generate_batches(
                project, existing, sources, inventory
            )
            document = merge_specifications(existing, generated)
            document = self._mark_unreconciled_rules(
                document,
                stale_rule_keys,
                generated,
                sources,
                inventory,
            )
            document = self._enrich_source_refs(document, inventory)
            await self._write(location, document)
            return "updated"
        except (ValidationError, ValueError) as exception:
            logger.warning(
                "项目规范模型输出无效 action=project.specification.refresh projectId=%s",
                project.id,
            )
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception
        except AppException:
            raise
        except Exception as exception:
            logger.exception(
                "项目规范构建失败 action=project.specification.refresh projectId=%s",
                project.id,
            )
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception

    async def _generate_batches(
        self,
        project,
        existing: ProjectSpecificationDocument | None,
        sources: list[dict[str, Any]],
        inventory: list[dict[str, Any]],
    ) -> ProjectSpecificationDocument:
        """仅合并完整批次；截断时二分候选，最小批次仍失败则保留旧规范。"""
        assert self._generator is not None
        pending = deque(self._batch_sources(sources) or [[]])
        generated: ProjectSpecificationDocument | None = None
        completed = 0
        while pending:
            batch = pending.popleft()
            candidate_count = sum(len(item["rule_candidates"]) for item in batch)
            current = (
                merge_specifications(existing, generated)
                if generated is not None
                else existing
            )
            logger.info(
                "开始生成项目规范批次 action=project.specification.batch "
                "projectId=%s batch=%s candidateCount=%s remainingBatches=%s",
                project.id,
                completed + 1,
                candidate_count,
                len(pending),
            )
            try:
                result = await self._generator.generate(
                    self._build_prompt(project, current, batch, inventory),
                    ProjectSpecificationDocument,
                    normalize_json=normalize_specification_json,
                )
            except StructuredOutputTruncatedError:
                if candidate_count <= 1:
                    raise
                smaller_batches = self._batch_sources(
                    batch, max_candidates=(candidate_count + 1) // 2
                )
                pending.extendleft(reversed(smaller_batches))
                logger.warning(
                    "项目规范批次输出被截断，拆分后重试 "
                    "action=project.specification.batch projectId=%s "
                    "candidateCount=%s splitCount=%s",
                    project.id,
                    candidate_count,
                    len(smaller_batches),
                )
                continue
            if result.project_id != project.id:
                raise ValueError("项目规范中的项目 ID 与当前项目不一致")
            generated = merge_specifications(generated, result)
            completed += 1
        assert generated is not None
        return generated

    def _batch_sources(
        self,
        sources: list[dict[str, Any]],
        *,
        max_candidates: int = _MAX_BATCH_CANDIDATES,
    ) -> list[list[dict[str, Any]]]:
        """按候选数量和文本长度分批，单个大文件也可拆分，不丢弃候选。"""
        batches: list[list[dict[str, Any]]] = []
        batch: list[dict[str, Any]] = []
        count = size = 0
        for source in sources:
            if not source["rule_candidates"]:
                size_of_source = len(json.dumps(source, ensure_ascii=False))
                if batch and size + size_of_source > self._MAX_BATCH_SOURCE_CHARS:
                    batches.append(batch)
                    batch = []
                    count = size = 0
                batch.append({**source, "rule_candidates": []})
                size += size_of_source
            for candidate in source["rule_candidates"]:
                entry = {**source, "rule_candidates": [candidate]}
                entry_size = len(json.dumps(entry, ensure_ascii=False))
                if batch and (
                    count >= max_candidates
                    or size + entry_size > self._MAX_BATCH_SOURCE_CHARS
                ):
                    batches.append(batch)
                    batch = []
                    count = size = 0
                if batch and batch[-1]["source_ref"] == source["source_ref"]:
                    batch[-1]["rule_candidates"].append(candidate)
                else:
                    batch.append(entry)
                count += 1
                size += entry_size
        if batch:
            batches.append(batch)
        return batches

    def _location(self, project):
        return self._locations.system_file(
            project.owner_user_id,
            project.id,
            "project_specification.json",
        )

    async def _load_existing(
        self,
        location,
        project_id: int,
    ) -> ProjectSpecificationDocument | None:
        """
        从云端读取 project_specification.json 文件，并验证项目 ID 是否一致。
        如果文件不存在，则返回 None。
        如果存在则加载并且验证文件归属
        """
        exists = await asyncio.to_thread(self._storage.exists, location)
        if not exists:
            return None
        document_bytes = await asyncio.to_thread(self._storage.read_bytes, location)
        try:
            document = ProjectSpecificationDocument.model_validate_json(document_bytes)
        except ValidationError as exception:
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED
            ) from exception
        if document.project_id != project_id:
            raise AppException(ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED)
        return document

    async def _write(self, location, document: ProjectSpecificationDocument) -> None:
        document_bytes = json.dumps(
            document.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        await asyncio.to_thread(
            self._storage.put_bytes,
            location,
            document_bytes,
            "application/json",
        )

    async def _load_rule_sources(
        self,
        project,
        files: Iterable[Any],
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        eligible = [
            file
            for file in files
            if self._is_current_project_file(file) and file.detail_ref
        ]
        for file in sorted(eligible, key=lambda item: item.relative_path):
            location = self._locations.system_file(
                project.owner_user_id,
                project.id,
                file.detail_ref.removeprefix("system/"),
            )
            if not await asyncio.to_thread(self._storage.exists, location):
                logger.warning(
                    "文件详情不存在，跳过规则候选 action=project.specification.source "
                    "projectId=%s fileId=%s",
                    project.id,
                    file.id,
                )
                continue
            detail_bytes = await asyncio.to_thread(self._storage.read_bytes, location)
            try:
                detail = FileDetail.model_validate_json(detail_bytes)
            except ValidationError:
                logger.warning(
                    "文件详情格式无效，跳过规则候选 action=project.specification.source "
                    "projectId=%s fileId=%s",
                    project.id,
                    file.id,
                )
                continue
            if not self._matches_file(detail, file):
                continue
            sources.append(
                {
                    "source_ref": self._inventory_item(file),
                    "summary": detail.summary,
                    "project_facts": detail.project_facts,
                    "rule_candidates": [
                        candidate.model_dump(mode="json")
                        for candidate in detail.rule_candidates
                    ],
                }
            )
        return sources

    def _build_prompt(
        self,
        project,
        existing: ProjectSpecificationDocument | None,
        sources: list[dict[str, Any]],
        inventory: list[dict[str, Any]],
    ) -> str:
        existing_json = (
            existing.model_dump_json(indent=2) if existing is not None else "null"
        )
        source_json = json.dumps(sources, ensure_ascii=False, indent=2)
        source_meta = json.dumps(
            {
                "project_id": str(project.id),
                "project_name": project.project_name,
                "source_selection": "全部当前有效文件详情中的结构化规则候选",
                "source_inventory_is_complete": True,
                "rule_candidates_are_partial": True,
                "current_sources": inventory,
            },
            ensure_ascii=False,
            indent=2,
        )
        prompt = (
            f"{ProjectSpecificationPrompt.PROJECT_SPECIFICATION.value}"
            f"\n\n# 实际输入\nexisting_specification_json：\n{existing_json}"
            f"\n\nnew_content（结构化规则候选）：\n{source_json}"
            f"\n\nsource_meta：\n{source_meta}"
            "\n\n# 最终约束\n"
            f'project_id 必须为十进制字符串 "{project.id}"。'
            "规则引用文件时必须原样复制候选中的 file_id、path、"
            "content_hash 和 detail_ref；"
            "不得仅因某个文件没有规则候选就删除旧规则；"
            "只有旧规则引用的文件不在完整 current_sources 中时，"
            "才可基于来源删除将其标记为 deprecated 或 pending_review。"
            "本次 new_content 只包含一批规则候选；所有批次共享完整文件清单。"
            "只返回本批新增或需要修改的规则、变更和忽略项，不要重写整份旧规范。"
            "已存在的同一规则必须复用原 ID；更新条目须保留原有来源和历史。"
            "没有变化的规则数组返回 []，development_stage 没有新证据时省略。"
            "project_facts 是阶段、能力和日期等事实，须保留已完成与计划中的区别，只用于 development_stage，不升级为项目规范规则。"
            "不得把当前批次没有提供某条候选视为规则被删除。"
            "每条规则和变更说明使用简洁中文，不复制候选全文或旧 changes。"
        )
        try:
            return sanitize_sensitive_content(prompt).text
        except SensitiveContentBlockedError as exception:
            raise AppException(
                ErrorCode.PROJECT_SPECIFICATION_BUILD_FAILED,
                "项目规范来源包含禁止发送至模型的私钥内容",
            ) from exception

    def _build_inventory(self, files: Iterable[Any]) -> list[dict[str, Any]]:
        """
        构建项目文件清单。
        根据给定的文件列表，过滤并构建当前项目的文件清单。
        """
        return [
            self._inventory_item(file)
            for file in sorted(files, key=lambda item: item.relative_path)
            if self._is_current_project_file(file)
        ]

    @staticmethod
    def _is_current_project_file(file: Any) -> bool:
        """判断文件是否属于当前项目的有效文件"""
        return (
            file.business_code == "project"
            and file.status == "active"
            and file.upload_status == "success"
        )

    @staticmethod
    def _inventory_item(file: Any) -> dict[str, Any]:
        """构建详情文件的文件元信息"""
        file_type = "doc" if file.file_type == "doc" else "code"
        return {
            "type": file_type,
            "file_id": file.id,
            "path": file.relative_path,
            "content_hash": file.content_hash,
            "detail_ref": file.detail_ref or "",
        }

    @staticmethod
    def _matches_file(detail: FileDetail, file: Any) -> bool:
        return (
            detail.file_id == file.id
            and detail.content_hash == file.content_hash
            and detail.detail_ref == file.detail_ref
        )

    def _enrich_source_refs(
        self,
        document: ProjectSpecificationDocument,
        inventory: list[dict[str, Any]],
    ) -> ProjectSpecificationDocument:
        by_id = {item["file_id"]: item for item in inventory}
        by_path = {item["path"]: item for item in inventory}

        def enrich(ref: SpecificationSourceRef) -> SpecificationSourceRef:
            source = by_id.get(ref.file_id) if ref.file_id is not None else None
            source = source or by_path.get(ref.path)
            if source is None or ref.type not in {"doc", "code"}:
                return ref
            return ref.model_copy(
                update={
                    "type": source["type"],
                    "path": source["path"],
                    "file_id": source["file_id"],
                    "content_hash": source["content_hash"],
                    "detail_ref": source["detail_ref"],
                }
            )

        body = document.project_specification
        updates: dict[str, Any] = {}
        for field_name in self._RULE_FIELDS:
            rules = getattr(body, field_name)
            updates[field_name] = [
                rule.model_copy(
                    update={"source_refs": [enrich(ref) for ref in rule.source_refs]}
                )
                for rule in rules
            ]
        return document.model_copy(
            update={"project_specification": body.model_copy(update=updates)}
        )

    def _requires_reconciliation(
        self,
        existing: ProjectSpecificationDocument | None,
        inventory: list[dict[str, Any]],
    ) -> bool:
        return bool(self._stale_rule_keys(existing, inventory))

    def _stale_rule_keys(
        self,
        existing: ProjectSpecificationDocument | None,
        inventory: list[dict[str, Any]],
    ) -> set[tuple[str, str]]:
        if existing is None:
            return set()
        by_id = {item["file_id"]: item for item in inventory}
        by_path = {item["path"]: item for item in inventory}
        stale: set[tuple[str, str]] = set()
        body = existing.project_specification
        for field_name in self._RULE_FIELDS:
            for rule in getattr(body, field_name):
                for ref in rule.source_refs:
                    if ref.type not in {"doc", "code"}:
                        continue
                    source = by_id.get(ref.file_id) if ref.file_id is not None else None
                    source = source or by_path.get(ref.path)
                    if source is None or self._source_ref_changed(ref, source):
                        stale.add((field_name, rule.id))
                        break
        return stale

    @staticmethod
    def _source_ref_changed(
        ref: SpecificationSourceRef,
        source: dict[str, Any],
    ) -> bool:
        return (
            ref.file_id != source["file_id"]
            or ref.path != source["path"]
            or ref.content_hash != source["content_hash"]
            or ref.detail_ref != source["detail_ref"]
        )

    def _mark_unreconciled_rules(
        self,
        document: ProjectSpecificationDocument,
        stale_rule_keys: set[tuple[str, str]],
        generated: ProjectSpecificationDocument,
        sources: list[dict[str, Any]],
        inventory: list[dict[str, Any]],
    ) -> ProjectSpecificationDocument:
        generated_keys = {
            (field_name, rule.id)
            for field_name in self._RULE_FIELDS
            for rule in getattr(generated.project_specification, field_name)
        }
        candidate_sources = {
            (
                item["source_ref"]["file_id"],
                item["source_ref"]["content_hash"],
                item["source_ref"]["detail_ref"],
            )
            for item in sources
        }
        body = document.project_specification
        updates: dict[str, Any] = {}
        for field_name in self._RULE_FIELDS:
            updated_rules = []
            for rule in getattr(body, field_name):
                key = (field_name, rule.id)
                unresolved_source = self._has_unresolved_source(rule, inventory)
                confirmed = key in generated_keys and any(
                    (ref.file_id, ref.content_hash, ref.detail_ref) in candidate_sources
                    for ref in rule.source_refs
                    if ref.type in {"doc", "code"}
                )
                needs_review = unresolved_source or (
                    key in stale_rule_keys and not confirmed
                )
                if needs_review and rule.status == "active":
                    rule = rule.model_copy(
                        update={
                            "status": "pending_review",
                            "updated_at": datetime.now(),
                        }
                    )
                updated_rules.append(rule)
            updates[field_name] = updated_rules
        return document.model_copy(
            update={"project_specification": body.model_copy(update=updates)}
        )

    def _has_unresolved_source(
        self,
        rule: Any,
        inventory: list[dict[str, Any]],
    ) -> bool:
        by_id = {item["file_id"]: item for item in inventory}
        by_path = {item["path"]: item for item in inventory}
        for ref in rule.source_refs:
            if ref.type not in {"doc", "code"}:
                continue
            source = by_id.get(ref.file_id) if ref.file_id is not None else None
            source = source or by_path.get(ref.path)
            if source is None or self._source_ref_changed(ref, source):
                return True
        return False
