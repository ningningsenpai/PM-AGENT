"""隔离联调环境与本地费用账本；不覆盖主服务配置或泄露密钥。"""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SERVICE = ROOT.parents[1]
REPO = SERVICE.parent


def configure(campaign: str):
    if not campaign or any(
        char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for char in campaign
    ):
        raise ValueError("测试活动 ID 只能包含字母、数字、短横线和下划线")
    output = ROOT / "output" / campaign
    output.mkdir(parents=True, exist_ok=True)
    private = ROOT / ".env.local"
    if not private.exists():
        private.write_text(
            f"FLOW_MYSQL_PASSWORD={secrets.token_hex(18)}\nFLOW_MINIO_USER=assistant-test\nFLOW_MINIO_PASSWORD={secrets.token_hex(18)}\nFLOW_JWT_SECRET={secrets.token_hex(32)}\n",
            encoding="utf-8",
        )
    values = dict(
        line.split("=", 1)
        for line in private.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    os.environ.update(
        {
            "PM_AGENT_DATABASE_URL": f"mysql+asyncmy://root:{values['FLOW_MYSQL_PASSWORD']}@127.0.0.1:19306/pm_agent_assistant_test?charset=utf8mb4",
            "PM_AGENT_REDIS_URL": "redis://127.0.0.1:19379/3",
            "PM_AGENT_REDIS_KEY_PREFIX": f"assistant-test:{campaign}",
            "MINIO_ENDPOINT": "127.0.0.1:19000",
            "MINIO_ROOT_USER": values["FLOW_MINIO_USER"],
            "MINIO_ROOT_PASSWORD": values["FLOW_MINIO_PASSWORD"],
            "MINIO_BUCKET": "pm-agent-assistant-test",
            "MINIO_SECURE": "false",
            "PM_AGENT_JWT_SECRET": values["FLOW_JWT_SECRET"],
            "PM_AGENT_SNOWFLAKE_NODE_ID": "57",
            "PM_AGENT_TEST_BUDGET_PATH": str(output / "费用账本.sqlite"),
            "PM_AGENT_TEST_BUDGET_CNY": "30",
            "PM_AGENT_LLM_TRACE_DIR": str(output / "模型调用原始轨迹"),
        }
    )
    sys.path.insert(0, str(SERVICE))
    from app.core.config.load_env_file import load_env_file

    load_env_file()
    return output


if __name__ == "__main__":
    from cli import ChineseArgumentParser

    parser = ChineseArgumentParser(description="隔离测试环境启动与健康检查")
    parser.add_argument("action", choices=["configure", "check", "migrate", "serve"])
    parser.add_argument("--campaign", required=True)
    args = parser.parse_args()
    output = configure(args.campaign)
    if args.action == "configure":
        print("测试环境已配置，密钥仅保存于被忽略的 .env.local")
    elif args.action == "migrate":
        from alembic import command
        from alembic.config import Config

        os.chdir(SERVICE)
        command.upgrade(Config("alembic.ini"), "head")
    elif args.action == "check":
        import asyncio

        from app.infrastructure.database import get_engine
        from app.infrastructure.redis import get_redis_provider
        from app.infrastructure.storage import StorageLocation, get_object_storage
        from sqlalchemy import text

        async def check():
            engine = get_engine()
            async with engine.connect() as connection:
                name = await connection.scalar(text("SELECT DATABASE()"))
            redis = get_redis_provider().client
            await redis.ping()
            await redis.aclose()
            storage = get_object_storage()
            location = StorageLocation(
                "pm-agent-assistant-test", f"health/{args.campaign}.txt"
            )
            await asyncio.to_thread(
                storage.put_bytes, location, b"assistant-test", "text/plain"
            )
            assert (
                await asyncio.to_thread(storage.read_bytes, location)
                == b"assistant-test"
            )
            await engine.dispose()
            result = {
                "database": name,
                "redis": "19379/3",
                "minio": "19000/pm-agent-assistant-test",
                "status": "正常",
            }
            (output / "环境连接检查.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(json.dumps(result, ensure_ascii=False))

        asyncio.run(check())
    else:
        import uvicorn

        uvicorn.run("app.main:app", host="127.0.0.1", port=18080, reload=False)
