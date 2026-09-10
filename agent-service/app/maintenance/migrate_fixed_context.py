"""把旧 Context 正式内容和学习草稿迁回固定文件与 MySQL。"""

from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path

from sqlalchemy import select

from app.core.errors import AppException, ErrorCode
from app.core.time import legacy_utc_to_shanghai, shanghai_now
from app.infrastructure.database import get_engine, get_session_factory
from app.infrastructure.storage import get_object_storage
from app.modules.chat.context.fixed_store import FORMAL_FILES, FixedContextStore
from app.modules.chat.context.models import AgentContextEntry
from app.modules.chat.context.serialization import entry_data
from app.modules.chat.context.store import ContextStore
from app.modules.chat.learning.models import AgentLearningDraft
from app.modules.chat.learning.store import DraftStore, LegacyDraftStore
from app.modules.project.models import Project


class MigrationDraftRepository:
    """迁移命令专用的数据访问适配器，避免跨模块依赖业务仓储。"""

    def __init__(self, session):
        self.session = session

    async def get(self, user_id, project_id, draft_id, *, lock=False):
        statement = select(AgentLearningDraft).where(
            AgentLearningDraft.id == draft_id,
            AgentLearningDraft.user_id == user_id,
            AgentLearningDraft.project_id == project_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def add(self, draft):
        self.session.add(draft)


def file_hash(document) -> str:
    return hashlib.sha256(
        json.dumps(document, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def normalize_legacy_expiry(entry):
    result = copy.deepcopy(entry)
    expires = result.get("expiresAt")
    if expires:
        from datetime import datetime

        parsed = datetime.fromisoformat(expires.replace("Z", "+00:00"))
        result["expiresAt"] = legacy_utc_to_shanghai(parsed).isoformat()
    return result


async def migrate_project(
    project, fixed, legacy, drafts, database_entries, *, apply_changes
):
    user_id, project_id = project.owner_user_id, project.id
    report = {
        "projectId": str(project_id),
        "userId": str(user_id),
        "files": {},
        "conflicts": [],
        "unclassified": [],
        "drafts": {"found": 0, "migrated": 0, "existing": 0, "failed": []},
    }
    snapshots = [
        await legacy.load(user_id, None),
        await legacy.load(user_id, project_id),
    ]
    manifest_entries = [
        normalize_legacy_expiry(entry)
        for snapshot in snapshots
        if snapshot.manifest is not None
        for entry in snapshot.entries
    ]
    # Manifest 是旧实现的最终正式状态；仅当其中缺失时才使用旧数据库正文补齐。
    by_id = {item["id"]: normalize_legacy_expiry(item) for item in database_entries}
    by_id.update({item["id"]: item for item in manifest_entries})
    legacy_entries = list(by_id.values())
    grouped = {path: [] for path in FORMAL_FILES}
    for entry in legacy_entries:
        try:
            grouped[fixed.target_for(entry)].append(entry)
        except (KeyError, TypeError, ValueError) as exception:
            report["unclassified"].append(
                {"entry": entry, "error": type(exception).__name__}
            )
    for path in FORMAL_FILES:
        document, etag = await fixed.read(user_id, project_id, path)
        before_hash = file_hash(document)
        current = {
            entry["id"]: entry
            for entry in fixed.document_entries(user_id, project_id, path, document)
        }
        changes = []
        for entry in grouped[path]:
            before = current.get(entry["id"])
            if before == entry:
                continue
            if before and before["content"] != entry["content"]:
                report["conflicts"].append(
                    {
                        "targetFile": path,
                        "entryId": entry["id"],
                        "fixedContent": before["content"],
                        "manifestContent": entry["content"],
                        "resolution": "manifest",
                    }
                )
            entry.setdefault("attributes", {})["targetFile"] = path
            changes.append(
                {
                    "entryId": entry["id"],
                    "before": before or {},
                    "after": entry,
                    "version": entry["version"],
                    "reason": "从旧 Context Manifest 迁回固定正式文件",
                    "sourceMessageId": entry.get("sourceMessageId"),
                }
            )
        revision = etag
        if changes and apply_changes:
            revision = (
                await fixed.apply(user_id, project_id, path, changes, etag)
            ).revision
            document, _etag = await fixed.read(user_id, project_id, path)
        report["files"][path] = {
            "beforeHash": before_hash,
            "afterHash": file_hash(document),
            "merged": len(changes),
            "revision": revision,
        }

    old_drafts = await LegacyDraftStore(legacy).list(user_id, project_id)
    report["drafts"]["found"] = len(old_drafts)
    snapshots = await fixed.snapshots(user_id, project_id)
    file_base = {
        path: etag
        for snapshot in snapshots.values()
        for path, etag in snapshot.files.items()
    }
    existing = [entry for snapshot in snapshots.values() for entry in snapshot.entries]
    for old in old_drafts:
        source_hash = file_hash(old)
        migrated = copy.deepcopy(old)
        migrated["state"] = {
            "publishing": "updating",
            "published": "applied",
        }.get(migrated.get("state"), migrated.get("state", "pending"))
        migrated["base"] = {
            key: snapshot.revision for key, snapshot in snapshots.items()
        }
        migrated["fileBase"] = file_base
        migrated["existing"] = existing
        migrated["migration"] = {
            "source": "legacy-context-store",
            "sourceHash": source_hash,
        }
        migrated.setdefault("history", []).append(
            {
                "version": migrated.get("version", 1),
                "reason": "从旧 MinIO 草稿迁移到 MySQL",
                "createdAt": shanghai_now().isoformat(),
            }
        )
        try:
            current, _lock = await drafts.load(user_id, project_id, old["id"])
            if current.get("migration", {}).get("sourceHash") == source_hash:
                report["drafts"]["existing"] += 1
                continue
            report["drafts"]["failed"].append(
                {"draftId": old["id"], "error": "MySQL 中已存在不同草稿"}
            )
            continue
        except AppException as exception:
            if exception.error is not ErrorCode.PARAM_INVALID:
                raise
        if apply_changes:
            await drafts.save(migrated, None)
        report["drafts"]["migrated"] += 1
    return report


async def run(apply_changes: bool, report_path: Path):
    storage = get_object_storage()
    from app.core.config import get_settings

    bucket = get_settings().storage.bucket
    fixed = FixedContextStore(storage, bucket)
    legacy = ContextStore(storage, bucket)
    reports = []
    session_factory = get_session_factory()
    async with session_factory() as session:
        projects = list(
            (await session.scalars(select(Project).order_by(Project.id))).all()
        )
        drafts = DraftStore(MigrationDraftRepository(session))
        for project in projects:
            rows = list(
                (
                    await session.scalars(
                        select(AgentContextEntry).where(
                            AgentContextEntry.user_id == project.owner_user_id,
                            (
                                (AgentContextEntry.project_id == project.id)
                                | AgentContextEntry.project_id.is_(None)
                            ),
                        )
                    )
                ).all()
            )
            reports.append(
                await migrate_project(
                    project,
                    fixed,
                    legacy,
                    drafts,
                    [entry_data(row) for row in rows],
                    apply_changes=apply_changes,
                )
            )
    payload = {
        "mode": "apply" if apply_changes else "dry-run",
        "generatedAt": shanghai_now().isoformat(),
        "projectCount": len(reports),
        "projects": reports,
    }
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    await get_engine().dispose()


def main():
    parser = argparse.ArgumentParser(description="迁移旧 Context 内容与学习草稿")
    parser.add_argument(
        "--apply", action="store_true", help="实际写入；默认只生成核对报告"
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("context-migration-report.json"),
        help="核对报告路径",
    )
    arguments = parser.parse_args()
    asyncio.run(run(arguments.apply, arguments.report.resolve()))


if __name__ == "__main__":
    main()
