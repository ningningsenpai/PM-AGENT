"""通过真实 HTTP、MySQL、MinIO 和模型调用执行七轮上下文基准。"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import inspect, text

from app.core.config import get_settings
from app.infrastructure.database import get_engine
from app.infrastructure.storage import StorageLocation, get_object_storage

ROOT = Path(__file__).resolve().parent
SYSTEM_FILES = (
    "index.json",
    "project_specification.json",
    "project_specification/development_approach.json",
    "project_specification/technical_constraints.json",
    "project_specification/coding_rules.json",
    "project_specification/document_rules.json",
    "project_specification/risk_rules.json",
    "long_term_memory.json",
    "short_term_memory.json",
    "user_habits/work.json",
    "user_habits/thinking.json",
    "user_habits/specification.json",
    "user_habits/tooling.json",
    "user_habits/life.json",
    "update_journal.jsonl",
)
RULE_FILES = tuple(
    path for path in SYSTEM_FILES if path.startswith("project_specification/")
)

INITIAL_DOCUMENT = """# 星河工单台项目规划

## 当前进度

- 用户认证和项目文件上传已经完成并通过测试。
- 当前正在实现项目上下文分析与项目助手问答。

## 下一阶段目标

- 完成订单查询接口与发布前回归测试。

## 必须遵守的项目约束

1. 所有 Python 代码注释必须使用简体中文。
2. 项目只能使用 FastAPI、MySQL、Redis 和 MinIO，不能引入消息队列。
3. API Key、访问令牌和数据库密码不得写入项目文件。
4. 架构设计文档必须记录关键方案的取舍理由。
"""

UPDATED_DOCUMENT = """# 星河工单台项目规划

## 当前进度

- 用户认证、项目文件上传和项目上下文分析已经完成并通过测试。
- 当前正在实现订单查询接口。

## 下一阶段目标

- 完成订单查询接口、权限回归和发布检查。

## 必须遵守的项目约束

1. 所有 Python 代码注释必须使用简体中文。
2. 项目只能使用 FastAPI、MySQL、Redis 和 MinIO，不能引入消息队列。
3. API Key、访问令牌和数据库密码不得写入项目文件。
4. 架构设计文档必须记录关键方案的取舍理由与回滚方案。
5. 对外接口变更必须同步更新 Markdown 接口文档。
"""

INITIAL_CODE = '''"""订单查询服务。"""


class OrderService:
    def list_orders(self) -> list[dict]:
        # 返回当前用户可见的订单
        return []
'''

UPDATED_CODE = '''"""订单查询服务。"""


class OrderService:
    def list_orders(self, user_id: int) -> list[dict]:
        # 按用户权限返回订单
        return [{"id": 1, "ownerId": user_id, "status": "ready"}]
'''


def save_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


class Benchmark:
    def __init__(self, base_url: str, output: Path) -> None:
        self.output = output
        self.output.mkdir(parents=True, exist_ok=True)
        self.http = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=1200,
            trust_env=False,
        )
        self.token = ""
        self.user_id = 0
        self.project_id = 0
        self.conversation_id = 0
        self.storage = get_object_storage()
        self.bucket = get_settings().storage.bucket
        self.rounds: list[dict[str, Any]] = []

    def close(self) -> None:
        self.http.close()

    def request(self, label: str, method: str, path: str, **kwargs) -> Any:
        headers = {
            "X-Trace-Id": f"baseline-{label}-{uuid4().hex}",
            "X-Idempotency-Key": f"baseline-{label}-{uuid4().hex}",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        started = time.perf_counter()
        response = self.http.request(method, path, headers=headers, **kwargs)
        try:
            body = response.json()
        except ValueError as exception:
            raise AssertionError(
                f"{label} 未返回 JSON：HTTP {response.status_code}"
            ) from exception
        record = {
            "label": label,
            "method": method,
            "path": path,
            "httpStatus": response.status_code,
            "elapsedMs": round((time.perf_counter() - started) * 1000, 2),
            "response": body,
        }
        raw = json.dumps(record, ensure_ascii=False)
        if self.token:
            raw = raw.replace(self.token, "[已隐藏]")
        save_json(
            self.output / "requests" / f"{label}-{uuid4().hex[:8]}.json",
            json.loads(raw),
        )
        if response.status_code >= 400 or body.get("code") != 200:
            raise AssertionError(
                f"{label} 请求失败：HTTP {response.status_code}，{body.get('message')}"
            )
        return body.get("data")

    def location(self, relative_path: str) -> StorageLocation:
        return StorageLocation(
            self.bucket,
            f"PM-AGENT/{self.user_id}/{self.project_id}/system/{relative_path}",
        )

    def read_bytes(self, relative_path: str) -> bytes:
        return self.storage.read_bytes(self.location(relative_path))

    def read_json(self, relative_path: str) -> dict:
        return json.loads(self.read_bytes(relative_path))

    def hashes(self, paths=SYSTEM_FILES) -> dict[str, str]:
        return {
            path: hashlib.sha256(self.read_bytes(path)).hexdigest() for path in paths
        }

    def rules(self) -> list[dict[str, Any]]:
        return [
            {"section": path, **rule}
            for path in RULE_FILES
            for rule in self.read_json(path).get("rules", [])
        ]

    @staticmethod
    def rule_text(rule: dict[str, Any]) -> str:
        return str(rule.get("rule") or rule.get("constraint") or "")

    def add_round(
        self,
        number: int,
        name: str,
        checks: dict[str, bool],
        observed: dict[str, Any],
    ) -> None:
        result = {
            "round": number,
            "name": name,
            "passed": all(checks.values()),
            "checks": checks,
            "observed": observed,
        }
        self.rounds.append(result)
        save_json(self.output / "rounds" / f"{number:02d}-{name}.json", result)
        status = "通过" if result["passed"] else "失败"
        print(f"第 {number} 轮 {name}：{status}", flush=True)
        if not result["passed"]:
            failed = [key for key, passed in checks.items() if not passed]
            raise AssertionError(f"第 {number} 轮未通过：{'、'.join(failed)}")

    def upload(self, label: str, relative_path: str, content: str) -> dict:
        return self.request(
            label,
            "POST",
            f"/api/v1/projects/{self.project_id}/files",
            data={
                "relativePath": relative_path,
                "sourceMtimeMs": str(time.time_ns() // 1_000_000),
            },
            files={"file": (Path(relative_path).name, content.encode(), "text/plain")},
        )

    def overwrite(self, label: str, file: dict, content: str) -> dict:
        return self.request(
            label,
            "PUT",
            f"/api/v1/projects/{self.project_id}/files/{file['id']}/content",
            data={
                "sourceMtimeMs": str(time.time_ns() // 1_000_000),
                "lockVersion": str(file["lockVersion"]),
            },
            files={"file": (file["fileName"], content.encode(), "text/plain")},
        )

    def list_files(self) -> list[dict]:
        return self.request(
            f"list-files-{uuid4().hex[:6]}",
            "GET",
            f"/api/v1/projects/{self.project_id}/files",
        )

    def parse(self, label: str) -> dict:
        return self.request(
            label,
            "POST",
            f"/api/v1/projects/{self.project_id}/files/parse/init",
        )

    def ask(self, label: str, content: str) -> dict:
        return self.request(
            label,
            "POST",
            f"/api/v1/agent/conversations/{self.conversation_id}/messages",
            json={"content": content},
        )

    def setup(self) -> None:
        marker = uuid4().hex[:12]
        account = {
            "username": f"基准用户-{marker}",
            "email": f"minio-flow-{marker}@example.test",
            "password": f"Flow-{uuid4().hex}!",
        }
        self.request("register", "POST", "/api/v1/auth/register", json=account)
        login = self.request(
            "login",
            "POST",
            "/api/v1/auth/login",
            json={"email": account["email"], "password": account["password"]},
        )
        self.token = login["tokenValue"]
        self.user_id = int(login["user"]["id"])
        project = self.request(
            "create-project",
            "POST",
            "/api/v1/projects",
            json={"projectName": f"MinIO 主链路基准-{marker}"},
        )
        self.project_id = int(project["id"])

    def round_1_initialization(self, database: dict[str, Any]) -> None:
        prefix = f"PM-AGENT/{self.user_id}/{self.project_id}/system/"
        objects = {
            item.object_key.removeprefix(prefix)
            for item in self.storage.list_prefix(StorageLocation(self.bucket, prefix))
        }
        manifest = self.read_json("project_specification.json")
        index = self.read_json("index.json")
        expected_tables = {
            "alembic_version",
            "pm_user",
            "pm_project",
            "pm_project_file",
            "agent_conversation",
            "agent_message",
            "agent_run",
            "agent_learning_draft",
            "pm_report",
        }
        self.add_round(
            1,
            "项目初始化",
            {
                "15 个系统文件均已创建": set(SYSTEM_FILES) <= objects,
                "规则清单包含五个分区": set(manifest.get("sections", {}))
                == {Path(path).stem for path in RULE_FILES},
                "索引引用五个规则分区": len(
                    index.get("system", {}).get("project_specification_sections", {})
                )
                == 5,
                "MySQL 只保留必要业务表": set(database["tables"]) == expected_tables,
                "会话表不再保留学习游标": "learned_message_id"
                not in database["conversationColumns"],
            },
            {
                "systemObjects": sorted(objects),
                "database": database,
                "manifest": manifest,
                "indexSystem": index.get("system"),
            },
        )

    def round_2_initial_parse(self) -> None:
        self.upload("upload-plan", "docs/project-plan.md", INITIAL_DOCUMENT)
        self.upload("upload-code", "src/order_service.py", INITIAL_CODE)
        parse = self.parse("parse-initial")
        files = self.list_files()
        rules = self.rules()
        rule_texts = [self.rule_text(rule) for rule in rules]
        source_paths = [
            ref.get("path", "")
            for rule in rules
            for ref in rule.get("source_refs", [])
            if isinstance(ref, dict)
        ]
        details_exist = all(
            file.get("detailRef")
            and self.storage.exists(
                self.location(file["detailRef"].removeprefix("system/"))
            )
            for file in files
            if file.get("businessCode") == "project"
        )
        long_memory = self.read_json("long_term_memory.json")
        self.add_round(
            2,
            "初次文件解析",
            {
                "两个文件均完成语义解析": parse.get("successCount") == 2
                and parse.get("failureCount") == 0,
                "详情文件真实存在于 MinIO": details_exist,
                "文档约束进入规则分区": bool(rules)
                and any("注释" in text or "API Key" in text for text in rule_texts),
                "代码文件没有成为规则来源": not any(
                    path.endswith(".py") for path in source_paths
                ),
                "长期记忆写入可核验项目事实": bool(long_memory.get("long_term_memory")),
                "索引包含两个有效项目文件": self.read_json("index.json")
                .get("summary", {})
                .get("active_files")
                == 2,
            },
            {
                "parse": parse,
                "files": files,
                "rules": rules,
                "longTermMemory": long_memory,
            },
        )

    def round_3_unchanged_parse(self) -> None:
        before = self.hashes()
        parse = self.parse("parse-unchanged")
        after = self.hashes()
        self.add_round(
            3,
            "无变化重跑",
            {
                "没有重复解析文件": parse.get("candidateCount") == 0,
                "规则保持不变": all(before[path] == after[path] for path in RULE_FILES),
                "长期记忆保持不变": before["long_term_memory.json"]
                == after["long_term_memory.json"],
                "索引语义内容未膨胀": self.read_json("index.json")
                .get("summary", {})
                .get("active_files")
                == 2,
            },
            {"parse": parse, "before": before, "after": after},
        )

    def round_4_document_update(self) -> None:
        before = self.hashes()
        plan_file = next(
            file
            for file in self.list_files()
            if file["relativePath"] == "docs/project-plan.md"
        )
        self.overwrite("overwrite-plan", plan_file, UPDATED_DOCUMENT)
        parse = self.parse("parse-updated-plan")
        after = self.hashes()
        rules = self.rules()
        texts = [self.rule_text(rule) for rule in rules]
        memory = self.read_json("long_term_memory.json")
        self.add_round(
            4,
            "权威文档更新",
            {
                "只解析变化后的文档": parse.get("successCount") == 1
                and parse.get("failureCount") == 0,
                "文档规则已同步新要求": any(
                    "Markdown" in text or "接口文档" in text for text in texts
                ),
                "至少一个规则分区版本变化": any(
                    before[path] != after[path] for path in RULE_FILES
                ),
                "长期记忆反映新项目事实": any(
                    "上下文" in str(item) or "订单" in str(item)
                    for item in memory.get("long_term_memory", [])
                ),
                "规则清单哈希与条数已刷新": all(
                    reference.get("content_hash")
                    and isinstance(reference.get("item_count"), int)
                    for reference in self.read_json("project_specification.json")
                    .get("sections", {})
                    .values()
                ),
            },
            {
                "parse": parse,
                "rules": rules,
                "longTermMemory": memory,
                "changed": [
                    path for path in SYSTEM_FILES if before[path] != after[path]
                ],
            },
        )

    def round_5_code_update(self) -> None:
        before_rules = self.hashes(RULE_FILES)
        code_file = next(
            file
            for file in self.list_files()
            if file["relativePath"] == "src/order_service.py"
        )
        self.overwrite("overwrite-code", code_file, UPDATED_CODE)
        parse = self.parse("parse-updated-code")
        after_rules = self.hashes(RULE_FILES)
        files = self.list_files()
        code = next(
            file for file in files if file["relativePath"] == "src/order_service.py"
        )
        self.add_round(
            5,
            "代码更新边界",
            {
                "只解析变化后的代码": parse.get("successCount") == 1
                and parse.get("failureCount") == 0,
                "代码更新不会生成或改写规则": before_rules == after_rules,
                "代码详情引用已经刷新": bool(code.get("detailRef")),
                "索引中的代码哈希已刷新": any(
                    item.get("logical_path") == "src/order_service.py"
                    and item.get("content_hash")
                    == f"sha256:{code.get('contentHash')}"
                    for item in self.read_json("index.json").get("project", [])
                ),
            },
            {
                "parse": parse,
                "code": code,
                "ruleHashesBefore": before_rules,
                "ruleHashesAfter": after_rules,
            },
        )

    def round_6_explicit_rule(self) -> None:
        conversation = self.request(
            "create-conversation",
            "POST",
            "/api/v1/agent/conversations",
            json={"projectId": str(self.project_id), "title": "主链路验证"},
        )
        self.conversation_id = int(conversation["id"])
        message = "请把这条设置为本项目规则：所有 API 响应必须包含 traceId。"
        result = self.ask("chat-explicit-rule", message)
        rules = self.rules()
        update = result.get("result", {}).get(
            "contextUpdate", result.get("contextUpdate", {})
        )
        answer = result.get("result", {}).get("answer", result.get("answer", ""))
        self.add_round(
            6,
            "对话明确规则",
            {
                "请求运行成功": result.get("status") == "success",
                "多维计划识别上下文更新": bool(
                    result.get("result", {})
                    .get("requestPlan", {})
                    .get("context_updates")
                ),
                "规则在回答前直接生效": update.get("status") == "applied",
                "规则正文真实写入 MinIO": any(
                    "traceId" in self.rule_text(rule) for rule in rules
                ),
                "回答包含实际更新反馈": bool(answer),
            },
            {"run": result, "contextUpdate": update, "answer": answer, "rules": rules},
        )

    def round_7_preference_and_recall(self) -> None:
        habit_before = self.hashes(("user_habits/specification.json",))
        uncertain = self.ask(
            "chat-uncertain-preference",
            "我觉得以后也许可以使用表格回答项目进度。",
        )
        uncertain_update = uncertain.get("result", {}).get("contextUpdate", {})
        habit_after_uncertain = self.hashes(("user_habits/specification.json",))
        explicit = self.ask(
            "chat-explicit-preference",
            "以后回答项目进度时请给出详细的 Markdown 列表。",
        )
        explicit_update = explicit.get("result", {}).get("contextUpdate", {})
        query = self.ask(
            "chat-progress-query",
            "请分析当前项目进度，并给出下一阶段建议；说明事实依据，不要把建议说成已完成。",
        )
        query_result = query.get("result", {})
        answer = query_result.get("answer", "")
        habits = self.read_json("user_habits/specification.json").get("user_habits", [])
        self.add_round(
            7,
            "偏好确认与项目召回",
            {
                "不确定偏好只生成待确认草稿": uncertain_update.get("status")
                == "pending_confirmation"
                and bool(uncertain_update.get("draftId")),
                "待确认偏好未污染正式文件": habit_before == habit_after_uncertain,
                "明确偏好直接写入项目级文件": explicit_update.get("status") == "applied"
                and any("Markdown" in str(item) for item in habits),
                "复合问题被拆为进度和下一阶段": {
                    unit.get("action")
                    for unit in query_result.get("requestPlan", {}).get(
                        "request_units", []
                    )
                }
                >= {"analyze_project_progress", "draft_next_stage_tasks"},
                "回答召回真实项目内容": any(
                    term in answer for term in ("认证", "文件上传", "上下文", "订单")
                ),
                "回答区分事实与建议": "建议" in answer
                and any(word in answer for word in ("已完成", "完成", "当前")),
                "回答有真实内容而非空模板": len(answer.strip()) >= 80,
            },
            {
                "uncertain": uncertain,
                "explicit": explicit,
                "query": query,
                "habits": habits,
                "answer": answer,
            },
        )


async def database_snapshot() -> dict[str, Any]:
    engine = get_engine()
    async with engine.connect() as connection:
        table_names = list(
            await connection.run_sync(lambda conn: inspect(conn).get_table_names())
        )
        columns = [
            row[0]
            for row in (
                await connection.execute(text("SHOW COLUMNS FROM agent_conversation"))
            ).all()
        ]
    return {
        "tableCount": len(table_names),
        "tables": sorted(table_names),
        "conversationColumns": columns,
    }


def run(base_url: str, output: Path) -> int:
    benchmark = Benchmark(base_url, output)
    try:
        health = benchmark.http.get("/internal/health")
        if health.status_code != 200:
            raise AssertionError("后端健康检查未通过")
        database = asyncio.run(database_snapshot())
        benchmark.setup()
        benchmark.round_1_initialization(database)
        benchmark.round_2_initial_parse()
        benchmark.round_3_unchanged_parse()
        benchmark.round_4_document_update()
        benchmark.round_5_code_update()
        benchmark.round_6_explicit_rule()
        benchmark.round_7_preference_and_recall()
        summary = {
            "startedAt": datetime.now(UTC).isoformat(),
            "baseUrl": base_url,
            "userId": str(benchmark.user_id),
            "projectId": str(benchmark.project_id),
            "passed": all(item["passed"] for item in benchmark.rounds),
            "rounds": benchmark.rounds,
        }
        save_json(output / "baseline-summary.json", summary)
        print(f"七轮基准全部通过，结果目录：{output}", flush=True)
        return 0
    # 基准入口必须把任意业务失败写入证据文件，便于复查中断轮次。
    except Exception as exception:  # noqa: BLE001
        save_json(
            output / "baseline-failure.json",
            {
                "errorType": type(exception).__name__,
                "error": str(exception),
                "rounds": benchmark.rounds,
            },
        )
        print(f"七轮基准失败：{exception}", flush=True)
        return 1
    finally:
        benchmark.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 MinIO 上下文主链路七轮真实基准")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / datetime.now(UTC).strftime("%Y%m%d-%H%M%S"),
    )
    args = parser.parse_args()
    return run(args.base_url, args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
