"""联调基础设施快照归档；与模拟前端的 HTTP 脚本分开执行。"""

from __future__ import annotations

from cli import ChineseArgumentParser
import asyncio
from datetime import UTC, datetime
import json

from client import save
from environment import configure


async def archive(output):
    from sqlalchemy import text
    from app.infrastructure.database import get_engine
    from app.infrastructure.storage import StorageLocation, get_object_storage

    state = json.loads((output / "状态检查点.json").read_text(encoding="utf-8"))
    user_id, project_id = int(state["userId"]), int(state["projectId"])
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    root = output / "数据快照" / stamp
    root.mkdir(parents=True, exist_ok=True)
    engine = get_engine()
    async with engine.connect() as connection:
        owner = await connection.scalar(
            text("SELECT owner_user_id FROM pm_project WHERE id=:id"),
            {"id": project_id},
        )
        if owner != user_id:
            raise ValueError("检查点用户与项目归属不一致，不导出快照")
        tables = (
            "pm_project_file",
            "agent_conversation",
            "agent_run",
            "agent_context_entry",
            "agent_context_scope",
            "pm_report",
        )
        for table in tables:
            where = "project_id=:id"
            if table.startswith("agent_context"):
                where = "user_id=:user AND (project_id=:id OR project_id IS NULL)"
            rows = (
                (
                    await connection.execute(
                        text(f"SELECT * FROM {table} WHERE {where}"),
                        {"id": project_id, "user": user_id},
                    )
                )
                .mappings()
                .all()
            )
            (root / f"{table}.json").write_text(
                json.dumps(
                    [dict(row) for row in rows],
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
        related = {
            "agent_message": "SELECT m.* FROM agent_message m JOIN agent_conversation c ON c.id=m.conversation_id WHERE c.project_id=:id AND c.user_id=:user",
            "agent_context_change": "SELECT c.* FROM agent_context_change c JOIN agent_context_entry e ON e.id=c.entry_id WHERE e.user_id=:user AND (e.project_id=:id OR e.project_id IS NULL)",
        }
        for table, statement in related.items():
            rows = (
                (
                    await connection.execute(
                        text(statement), {"id": project_id, "user": user_id}
                    )
                )
                .mappings()
                .all()
            )
            (root / f"{table}.json").write_text(
                json.dumps(
                    [dict(row) for row in rows],
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )
    await engine.dispose()
    storage = get_object_storage()
    for label, prefix in (
        ("project", f"PM-AGENT/{user_id}/{project_id}/"),
        ("user-context", f"PM-AGENT/user_context/{user_id}/"),
    ):
        for location in await asyncio.to_thread(
            storage.list_prefix, StorageLocation("pm-agent-assistant-test", prefix)
        ):
            relative = location.object_key[len(prefix) :]
            target = (root / "minio" / label / relative).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError("快照对象路径越出本轮目录")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(await asyncio.to_thread(storage.read_bytes, location))
    save(
        root / "归档说明.json",
        {"userId": str(user_id), "projectId": str(project_id), "snapshotAt": stamp},
    )
    print(f"快照已保存：{root}")


if __name__ == "__main__":
    parser = ChineseArgumentParser(description="归档指定测试轮次的数据和 MinIO 对象")
    parser.add_argument("--campaign", default="mvp-20260908")
    parser.add_argument("--round", required=True)
    args = parser.parse_args()
    if not args.round.startswith("round-") or not args.round[6:].isdigit():
        raise ValueError("轮次必须为 round-数字")
    asyncio.run(archive(configure(args.campaign) / args.round))
