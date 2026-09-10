"""旧数据库和固定云端文件的一次性导入；原始来源与历史随新版本保存。"""

import json

from app.core.errors import AppException, ErrorCode

from .schemas import EntryView
from .store import digest, json_bytes

RULE_FIELDS = (
    "development_approach",
    "technical_constraints",
    "coding_rules",
    "document_rules",
    "risk_rules",
)


def stable_id(value):
    return str(int(digest(value.encode())[:15], 16) or 1)


def specification_entries(project_id, document):
    result = []
    root = document.get("project_specification", {})
    for field in RULE_FIELDS:
        for item in root.get(field, []):
            key = f"{field}:{item['id']}"
            entry_id = item.get("learning_entry_id") or stable_id(
                f"specification:{project_id}:{key}"
            )
            content = (
                item.get("rule")
                or item.get("constraint")
                or item.get("approach")
                or json.dumps(item, ensure_ascii=False)
            )
            result.append(
                EntryView(
                    id=entry_id,
                    project_id=project_id,
                    kind="project_rule",
                    content=content,
                    attributes={
                        "key": key,
                        "sourceType": "file_specification",
                        "original": item,
                        "field": field,
                        "targetFile": "project_specification.json",
                        "targetSection": field,
                        "originalId": item["id"],
                        "humanEdited": bool(item.get("human_edited")),
                        "originalKind": item.get("original_kind"),
                    },
                    status={"active": "active", "deprecated": "invalid"}.get(
                        item.get("status"), "pending"
                    ),
                    version=item.get("learning_version") or 1,
                    source_message_id=None,
                    expires_at=None,
                    conditions=[item["scope"]] if item.get("scope") else [],
                ).model_dump(mode="json", by_alias=True)
            )
    return result


async def legacy_cloud(store, user_id, project_id):
    if project_id is None:
        return [], [], None
    prefix = f"PM-AGENT/{user_id}/{project_id}/system/"
    entries, history, specification = [], [], None
    documents = [
        ("short_term_memory.json", "short_term_memory", "short_memory"),
        ("long_term_memory.json", "long_term_memory", "long_memory"),
    ]
    documents += [
        (f"user_habits/{category}.json", "user_habits", "habit")
        for category in ("work", "thinking", "specification", "tooling", "life")
    ]
    for path, key, kind in documents:
        stored = await store._read(store.location(prefix, path))
        if not stored:
            continue
        document = json.loads(stored[0])
        if str(document.get("project_id")) != str(project_id):
            raise AppException(ErrorCode.FORBIDDEN, "旧云端文件所属项目不一致")
        for index, item in enumerate(document.get(key, [])):
            if not isinstance(item, dict):
                raise AppException(
                    ErrorCode.PARAM_INVALID, "旧记忆格式无法迁移，请先核对原文件"
                )
            content = (
                item.get("content")
                or item.get("summary")
                or item.get("habit")
                or json.dumps(item, ensure_ascii=False)
            )
            entry = EntryView(
                id=stable_id(f"legacy:{user_id}:{project_id}:{path}:{index}"),
                project_id=project_id,
                kind=kind,
                content=content,
                attributes={
                    "key": item.get("key")
                    or item.get("title")
                    or f"历史内容 {index + 1}",
                    "sourceType": "legacy_cloud",
                    "sourcePath": path,
                    "original": item,
                },
                status={
                    "active": "active",
                    "confirmed": "active",
                    "invalid": "invalid",
                    "deprecated": "invalid",
                }.get(item.get("status"), "pending"),
                version=max(1, int(item.get("version", 1))),
                source_message_id=None,
                expires_at=item.get("expires_at") or item.get("expiresAt"),
            ).model_dump(mode="json", by_alias=True)
            entries.append(entry)
        # 原始文档包含来源、旧历史和忽略项，完整归档供核对。
        if (
            document.get(key)
            or document.get("changes")
            or document.get("ignored_items")
        ):
            ref = await store.immutable(
                store.prefix(user_id, project_id),
                "migration/" + digest(json_bytes(document)) + ".json",
                json_bytes(document),
            )
            history.append(
                {
                    "reason": "迁移旧云端文件",
                    "sourcePath": path,
                    "archive": ref.model_dump(),
                }
            )
    stored = await store._read(store.location(prefix, "project_specification.json"))
    if stored:
        from app.project_context.specification.schemas import (
            ProjectSpecificationDocument,
        )

        specification = ProjectSpecificationDocument.model_validate_json(
            stored[0]
        ).model_dump(mode="json")
        if str(specification["project_id"]) != str(project_id):
            raise AppException(ErrorCode.FORBIDDEN, "旧项目规范所属项目不一致")
        entries.extend(specification_entries(project_id, specification))
    return entries, history, specification
