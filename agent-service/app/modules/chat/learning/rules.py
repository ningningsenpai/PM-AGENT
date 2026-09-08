"""学习候选的来源、版本与确认规则；不访问数据库或模型。"""

import hashlib
import re
import unicodedata

from app.core.errors import AppException, ErrorCode


def normalized_key(value):
    return hashlib.sha256(
        "".join(unicodedata.normalize("NFKC", value).lower().split()).encode()
    ).hexdigest()


def validate_source(candidate, sources):
    source = sources.get(candidate.source_message_id)
    if not source or candidate.source_quote not in source:
        raise AppException(ErrorCode.PARAM_INVALID, "学习条目缺少可验证的用户消息原文")
    return source


def resolve_entry(
    candidate, scope_key, canonical_key, by_id, by_key, seen, expected_versions
):
    row = by_key.get((scope_key, candidate.kind, canonical_key))
    if candidate.replaces_entry_id:
        row = by_id.get(int(candidate.replaces_entry_id))
        if row is None or row.scope_key != scope_key:
            raise AppException(ErrorCode.FORBIDDEN, "纠正目标不属于当前用户和项目范围")
        if row.kind != candidate.kind:
            raise AppException(
                ErrorCode.PARAM_INVALID,
                "学习纠正不能隐式改变条目类型，请显式晋升",
            )
    if row and (row.id in seen or expected_versions.get(row.id) != row.version):
        raise AppException(
            ErrorCode.RESOURCE_CONFLICT, "学习期间条目版本发生变化或重复纠正"
        )
    if candidate.invalidate and row is None:
        raise AppException(ErrorCode.PARAM_INVALID, "失效操作必须关联已有条目")
    return row


def candidate_status(candidate, source, row, by_key):
    explicit = bool(
        re.search(
            r"记住|确认|更正|纠正|改为|改成|更新|偏好|习惯|简称|称为|取消|忘记|不再",
            source,
        )
    )
    status = (
        "invalid"
        if candidate.invalidate and explicit
        else "active"
        if candidate.confirmed and explicit
        else "pending"
    )
    if candidate.kind == "term" and status == "active":
        aliases = {normalized_key(alias) for alias in candidate.aliases}
        for existing_entry in by_key.values():
            if (
                existing_entry is row
                or existing_entry.kind != "term"
                or existing_entry.status != "active"
            ):
                continue
            existing_aliases = {
                normalized_key(alias)
                for alias in existing_entry.attributes.get("aliases", [])
            }
            if (
                aliases & existing_aliases
                and candidate.canonical != existing_entry.attributes.get("canonical")
            ):
                status = "pending"
                break
    if row is not None and row.status != "pending" and status == "pending":
        raise AppException(
            ErrorCode.PARAM_INVALID,
            "未经确认的候选不能覆盖已有生效或失效条目，请明确确认纠正内容后重新学习",
        )
    return status
