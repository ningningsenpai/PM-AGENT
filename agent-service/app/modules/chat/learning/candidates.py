"""学习候选到正式条目的受控转换，只生成计划，不访问存储。"""

import copy
from datetime import datetime, timedelta

from app.core.errors import AppException, ErrorCode
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content

from ..context.conflicts import conflicts
from ..context.schemas import EntryView
from .rules import validate_source
from .schemas import LearnedCandidate


def build_entries(draft, selected):
    entries = copy.deepcopy(draft["existing"])
    by_id = {e["id"]: e for e in entries}
    candidates = {c["id"]: c for c in draft["candidates"]}
    if len(set(selected)) != len(selected) or not set(selected) <= candidates.keys():
        raise AppException(ErrorCode.PARAM_INVALID, "所选候选不属于当前草稿或重复")
    sources = {m["id"]: m["content"] for m in draft["messages"]}
    sources.update({f["id"]: f["text"] for f in draft.get("feedback", [])})
    changed, used = [], set()
    for candidate_id in selected:
        proposal = LearnedCandidate.model_validate(candidates[candidate_id]["proposal"])
        validate_source(proposal, sources)
        pid = None if proposal.scope == "user" else draft["projectId"]
        target = (
            by_id.get(proposal.replaces_entry_id)
            if proposal.replaces_entry_id
            else None
        )
        if proposal.replaces_entry_id and (
            target is None
            or target["projectId"] != pid
            or target["kind"] != proposal.kind
        ):
            raise AppException(
                ErrorCode.FORBIDDEN, "纠正目标不属于候选的类型和作用范围"
            )
        if proposal.invalidate and target is None:
            raise AppException(ErrorCode.PARAM_INVALID, "失效操作必须关联已有条目")
        target_id = target["id"] if target else candidate_id
        if target_id in used:
            raise AppException(
                ErrorCode.PARAM_INVALID,
                "同一轮不能重复覆盖同一条目；拆分时应创建新条目并单独失效原条目",
            )
        used.add(target_id)
        before = copy.deepcopy(target) if target else {}
        deadline = proposal.expires_at
        if deadline is None and proposal.kind == "short_memory":
            deadline = datetime.fromisoformat(draft["createdAt"]) + timedelta(days=7)
        related = proposal.related_entry_ids
        allowed_relations = set(by_id) | set(candidates)
        if not set(related) <= allowed_relations:
            raise AppException(ErrorCode.FORBIDDEN, "关联条目不属于当前草稿和上下文")
        original_message = any(
            m["id"] == proposal.source_message_id for m in draft["messages"]
        )
        entry = EntryView(
            id=target_id,
            project_id=pid,
            kind=proposal.kind,
            content=sanitize_sensitive_content(proposal.content).text,
            attributes={
                "key": proposal.key,
                "aliases": proposal.aliases,
                "canonical": proposal.canonical,
                "sourceQuote": proposal.source_quote,
                "sourceType": "user_statement" if original_message else "user_feedback",
                "draftId": draft["id"],
                "draftVersion": draft["version"],
                "feedbackId": None if original_message else proposal.source_message_id,
                "coexistReason": proposal.coexist_reason,
                "humanEdited": True,
            },
            status="invalid" if proposal.invalidate else "active",
            version=before.get("version", 0) + 1,
            source_message_id=proposal.source_message_id if original_message else None,
            expires_at=deadline,
            conditions=proposal.conditions,
            related_entry_ids=related,
        ).model_dump(mode="json", by_alias=True)
        if target:
            entries[entries.index(target)] = entry
        else:
            entries.append(entry)
        changed.append(
            {
                "entryId": target_id,
                "before": before,
                "after": entry,
                "version": entry["version"],
                "reason": "用户确认学习草稿",
                "sourceMessageId": entry["sourceMessageId"],
            }
        )
    return entries, changed


def preview(draft):
    # 预览不改变状态；冲突与原文同时交给用户核对。
    entries, changes = build_entries(draft, [c["id"] for c in draft["candidates"]])
    ids = {c["entryId"] for c in changes}
    pairs = [
        {
            "leftId": a["id"],
            "rightId": b["id"],
            "left": a["content"],
            "right": b["content"],
        }
        for index, a in enumerate(entries)
        for b in entries[index + 1 :]
        if {a["id"], b["id"]} & ids and conflicts(a, b)
    ]
    return {**draft, "conflicts": pairs}
