"""对话多维分析结果到 MinIO 固定文件的受控更新。"""

from __future__ import annotations

import re
from collections import defaultdict
from hashlib import sha256

from app.core.identifiers import get_snowflake_id_generator
from app.core.time import shanghai_now
from app.modules.chat.context.migration import stable_id
from app.modules.chat.learning.candidates import build_entries
from app.modules.chat.learning.schemas import LearnedCandidate
from app.modules.chat.learning.store import DraftStore


class AutomaticContextUpdateService:
    """只执行后端已校验的上下文信号，不接受模型生成路径或编号。"""

    def __init__(self, contexts, draft_repository) -> None:
        self._contexts = contexts
        self._drafts = DraftStore(draft_repository)

    async def apply(
        self,
        *,
        user_id: int,
        project_id: int,
        conversation_id: int,
        message_id: int,
        message: str,
        plan,
    ) -> dict:
        signals = (
            [] if plan is None or plan.requires_clarification else plan.context_updates
        )
        if not signals:
            return {"status": "no_change", "targets": [], "draftId": None}

        snapshots = await self._contexts.snapshots(user_id, project_id)
        existing = [
            entry for snapshot in snapshots.values() for entry in snapshot.entries
        ]
        unique_proposals = {}
        for signal in signals:
            proposal = self._proposal(signal, message_id)
            identity = (proposal.kind, proposal.key, proposal.target_file)
            unique_proposals[identity] = (signal, proposal)

        direct, pending = [], []
        for signal, proposal in unique_proposals.values():
            matched = self._same_semantic_entry(existing, proposal)
            if matched is not None:
                if (
                    matched["content"] == proposal.content
                    and matched["status"] == "active"
                ):
                    continue
                proposal.replaces_entry_id = matched["id"]
            if (
                signal.operation == "upsert"
                and signal.explicitness == "explicit"
                and signal.confidence >= 0.85
                and not signal.requires_confirmation
            ):
                direct.append(proposal)
            else:
                pending.append(proposal)

        applied = await self._apply_direct(
            user_id,
            project_id,
            conversation_id,
            message_id,
            message,
            snapshots,
            existing,
            direct,
        )
        draft_id = await self._save_pending_draft(
            user_id,
            project_id,
            conversation_id,
            message_id,
            message,
            snapshots,
            existing,
            pending,
        )
        status = (
            "partial"
            if applied["failures"]
            else "applied_and_pending"
            if applied["targets"] and draft_id
            else "applied"
            if applied["targets"]
            else "pending_confirmation"
            if draft_id
            else "no_change"
        )
        return {
            "status": status,
            "targets": applied["targets"],
            "failures": applied["failures"],
            "draftId": draft_id,
        }

    async def _apply_direct(
        self,
        user_id,
        project_id,
        conversation_id,
        message_id,
        message,
        snapshots,
        existing,
        proposals,
    ) -> dict:
        if not proposals:
            return {"targets": [], "failures": []}
        draft = self._draft_payload(
            user_id,
            project_id,
            conversation_id,
            message_id,
            message,
            snapshots,
            existing,
            proposals,
            state="updating",
        )
        selected = [candidate["id"] for candidate in draft["candidates"]]
        _entries, changes = build_entries(draft, selected)
        grouped = defaultdict(list)
        for change in changes:
            change["reason"] = "用户明确指令自动更新"
            grouped[self._contexts.fixed.target_for(change["after"])].append(change)

        targets, failures = [], []
        for target, target_changes in grouped.items():
            try:
                receipt = await self._contexts.fixed.apply(
                    user_id,
                    project_id,
                    target,
                    target_changes,
                    draft["fileBase"].get(target),
                )
                targets.append(
                    {
                        "path": target,
                        "revision": receipt.revision,
                        "entryIds": [item["entryId"] for item in target_changes],
                    }
                )
            except Exception as exception:  # noqa: BLE001 -- 逐目标返回真实失败结果。
                failures.append(
                    {
                        "path": target,
                        "error": getattr(exception, "message", str(exception)),
                    }
                )
        return {"targets": targets, "failures": failures}

    async def _save_pending_draft(
        self,
        user_id,
        project_id,
        conversation_id,
        message_id,
        message,
        snapshots,
        existing,
        proposals,
    ) -> str | None:
        if not proposals:
            return None
        draft = self._draft_payload(
            user_id,
            project_id,
            conversation_id,
            message_id,
            message,
            snapshots,
            existing,
            proposals,
            state="pending",
        )
        build_entries(draft, [candidate["id"] for candidate in draft["candidates"]])
        await self._drafts.save(draft, None)
        return draft["id"]

    @staticmethod
    def _draft_payload(
        user_id,
        project_id,
        conversation_id,
        message_id,
        message,
        snapshots,
        existing,
        proposals,
        *,
        state,
    ) -> dict:
        draft_id = str(get_snowflake_id_generator().next_id())
        candidates = []
        for proposal in proposals:
            seed = f"{project_id}:{user_id}:{proposal.kind}:{proposal.key}"
            candidates.append(
                {
                    "id": stable_id(seed),
                    "proposal": proposal.model_dump(
                        mode="json", by_alias=True, exclude={"coexist_group"}
                    ),
                }
            )
        return {
            "id": draft_id,
            "userId": str(user_id),
            "projectId": str(project_id),
            "conversationId": str(conversation_id),
            "version": 1,
            "state": state,
            "createdAt": shanghai_now().isoformat(),
            "learnedMessageId": str(message_id),
            "base": {key: snapshot.revision for key, snapshot in snapshots.items()},
            "fileBase": {
                path: etag
                for snapshot in snapshots.values()
                for path, etag in snapshot.files.items()
            },
            "existing": existing,
            "messages": [{"id": str(message_id), "content": message}],
            "candidates": candidates,
            "feedback": [],
            "history": [],
            "plan": None,
            "publications": {},
        }

    @classmethod
    def _proposal(cls, signal, message_id: int) -> LearnedCandidate:
        target_section = None
        if signal.target == "user_preference":
            kind, key = "habit", cls._preference_key(signal.content)
            target_file = "user_habits/specification.json"
        elif signal.target == "long_term_memory":
            kind, key = "long_memory", cls._semantic_key("goal", signal.content)
            target_file = "long_term_memory.json"
        elif signal.target == "short_term_memory":
            kind, key = "short_memory", cls._semantic_key("focus", signal.content)
            target_file = "short_term_memory.json"
        else:
            kind = "project_rule"
            target_section = cls._rule_section(signal.content)
            key = cls._semantic_key(target_section, signal.content)
            target_file = f"project_specification/{target_section}.json"
        return LearnedCandidate(
            kind=kind,
            scope="project",
            key=key,
            content=signal.content.strip(),
            source_message_id=str(message_id),
            source_quote=signal.source_text,
            confirmed=False,
            target_file=target_file,
            target_section=target_section,
        )

    @staticmethod
    def _same_semantic_entry(existing: list[dict], proposal: LearnedCandidate):
        expected_kind = proposal.kind
        return next(
            (
                entry
                for entry in existing
                if entry.get("kind") == expected_kind
                and entry.get("attributes", {}).get("key") == proposal.key
                and entry.get("attributes", {}).get("targetFile")
                == proposal.target_file
            ),
            None,
        )

    @staticmethod
    def _preference_key(content: str) -> str:
        if any(word in content for word in ("详细", "简洁", "展开")):
            return "response.detail_level"
        if any(word in content for word in ("表格", "列表", "Markdown", "格式")):
            return "response.format"
        if "语气" in content:
            return "response.tone"
        if "语言" in content:
            return "response.language"
        return "response.general"

    @staticmethod
    def _rule_section(content: str) -> str:
        lowered = content.lower()
        if any(word in lowered for word in ("api key", "密钥", "风险", "泄露", "敏感")):
            return "risk_rules"
        if any(word in lowered for word in ("文档", "readme", "markdown", "说明书")):
            return "document_rules"
        if any(
            word in lowered for word in ("依赖", "版本", "框架", "数据库", "运行环境")
        ):
            return "technical_constraints"
        if any(
            word in lowered for word in ("流程", "分支", "设计模式", "架构", "开发方式")
        ):
            return "development_approach"
        return "coding_rules"

    @staticmethod
    def _semantic_key(prefix: str, content: str) -> str:
        compact = re.sub(r"\s+", "", content).lower()
        digest = sha256(compact.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}.{digest}"
