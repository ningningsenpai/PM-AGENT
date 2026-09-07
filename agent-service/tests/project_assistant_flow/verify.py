"""独立于调试调用的固定验收检查，不以 HTTP 200 代替业务结果。"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from client import save

EXPECTED_TOOLS = {
    "get_current_project",
    "list_owned_projects",
    "list_current_project_files",
    "retrieve_project_context",
    "list_context_entries",
    "get_project_report",
    "read_project_file_evidence",
    "get_context_changes",
}


def verify_round(flow):
    results = []

    def check(name, passed, details=None):
        results.append({"name": name, "passed": bool(passed), "details": details})
        save(flow.output / "测试结果" / "确定性验收.json", results)

    flow.status()
    check("本轮源码配置一致", not flow.state.get("mixedVersions", False))
    files = flow.state["files"]
    check(
        "六个固定文件解析成功",
        len(files) == 6 and all(file["analysisStatus"] == "success" for file in files),
    )
    check(
        "修改和删除均被规划执行",
        len(flow.state["plan"]["modified"]) == 1
        and len(flow.state["plan"]["deleted"]) == 1,
    )
    check(
        "实际注册目录为八个只读工具",
        {tool["function"]["name"] for tool in flow.state["tools"]["tools"]}
        == EXPECTED_TOOLS,
    )
    messages = flow.request("messages", "GET", flow.conversation_url + "/messages")
    check(
        "会话历史持久化",
        len(messages) >= 20
        and any(message["role"] == "assistant" for message in messages),
    )
    first = flow.request(
        "idempotency-first",
        "POST",
        flow.conversation_url + "/messages",
        key="fixed-idempotency-check",
        json={"content": "只回答：收到。"},
    )
    flow.run_result("idempotency", first)
    second = flow.request(
        "idempotency-repeat",
        "POST",
        flow.conversation_url + "/messages",
        key="fixed-idempotency-check",
        json={"content": "只回答：收到。"},
    )
    check(
        "相同请求不重复生成",
        first["runId"] == second["runId"] and first["result"] == second["result"],
    )
    conflict = flow.client.send(
        "idempotency-conflict",
        "POST",
        flow.conversation_url + "/messages",
        key="fixed-idempotency-check",
        json={"content": "不同请求"},
    )
    check("幂等键内容冲突", conflict.get("code") == 10003)
    all_entries = flow.request(
        "entry-current",
        "GET",
        "/api/v1/agent/context-entries",
        params={"projectId": flow.state["projectId"]},
    )
    before = flow.state["entriesBefore"]
    check(
        "四种学习内容已建立",
        {entry["kind"] for entry in before}
        == {"term", "habit", "short_memory", "long_memory"},
    )
    decisions = [
        entry
        for entry in all_entries
        if entry["kind"] == "long_memory" and "上线" in entry["content"]
    ]
    check(
        "纠正后仅最新版本有效",
        len(decisions) == 1
        and decisions[0]["version"] >= 2
        and ("8" in decisions[0]["content"] or "八" in decisions[0]["content"]),
        decisions,
    )
    other = flow.request(
        "other-project-context",
        "GET",
        "/api/v1/agent/context-entries",
        params={"projectId": flow.state["otherProjectId"]},
    )
    check(
        "通用词库与习惯复用且项目记忆隔离",
        {entry["kind"] for entry in other} == {"term", "habit"}
        and all(entry["projectId"] is None for entry in other),
    )
    if all_entries:
        entry = all_entries[0]
        conflict = flow.client.send(
            "version-conflict",
            "PATCH",
            f"/api/v1/agent/context-entries/{entry['id']}",
            json={
                "version": entry["version"] + 100,
                "status": "invalid",
                "reason": "验证旧版本不能覆盖",
            },
        )
        check("条目乐观版本冲突", conflict.get("code") == 10003)
    if not flow.state.get("lifecycleChecked"):
        short = next(
            (entry for entry in all_entries if entry["kind"] == "short_memory"), None
        )
        if short:
            expired = flow.request(
                "expire-memory",
                "PATCH",
                f"/api/v1/agent/context-entries/{short['id']}",
                json={
                    "version": short["version"],
                    "expiresAt": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                    "reason": "验证显式设置的期限",
                },
            )
            active = flow.request(
                "expired-filter",
                "GET",
                "/api/v1/agent/context-entries",
                params={"projectId": flow.state["projectId"]},
            )
            check(
                "过期记忆不召回", short["id"] not in {entry["id"] for entry in active}
            )
            promoted = flow.request(
                "promote-memory",
                "PATCH",
                f"/api/v1/agent/context-entries/{short['id']}",
                json={
                    "version": expired["version"],
                    "kind": "long_memory",
                    "reason": "验证用户显式晋升",
                },
            )
            check(
                "显式晋升清除默认期限",
                promoted["kind"] == "long_memory" and promoted["expiresAt"] is None,
            )
            flow.request(
                "invalidate-memory",
                "PATCH",
                f"/api/v1/agent/context-entries/{short['id']}",
                json={
                    "version": promoted["version"],
                    "status": "invalid",
                    "reason": "测试事项已结束，显式失效",
                },
            )
            active = flow.request(
                "invalid-filter",
                "GET",
                "/api/v1/agent/context-entries",
                params={"projectId": flow.state["projectId"]},
            )
            check(
                "失效内容不召回", short["id"] not in {entry["id"] for entry in active}
            )
            flow.state["lifecycleChecked"] = True
            flow.state["lifecycleResults"] = results[-3:]
            flow.checkpoint()
    else:
        results.extend(flow.state["lifecycleResults"])
    token = flow.client.token
    marker = uuid4().hex[:12]
    try:
        flow.client.token = ""
        login = {
            "username": f"隔离用户-{marker}",
            "email": f"isolation-{marker}@example.test",
            "password": f"Test-{uuid4().hex}",
        }
        flow.request("other-register", "POST", "/api/v1/auth/register", json=login)
        authenticated = flow.request(
            "other-login",
            "POST",
            "/api/v1/auth/login",
            json={"email": login["email"], "password": login["password"]},
        )
        flow.client.token = authenticated["tokenValue"]
        for name, path, params in [
            ("会话", flow.conversation_url + "/messages", None),
            ("运行", f"/api/v1/agent/runs/{first['runId']}", None),
            (
                "学习条目",
                "/api/v1/agent/context-entries",
                {"projectId": flow.state["projectId"]},
            ),
            ("报告", f"/api/v1/projects/{flow.state['projectId']}/reports", None),
        ]:
            body = flow.client.send("deny-foreign", "GET", path, params=params)
            check(f"跨用户{name}拒绝访问", body.get("code") in (20002, 30001))
    finally:
        flow.client.token = token
    flow.trace()
    successful_tools, protocol_valid, calls_finished = set(), True, True
    integrity_warnings = set()
    for path in (flow.output / "模型与工具轨迹").glob("*.json"):
        run = json.loads(path.read_text(encoding="utf-8"))
        for event in run.get("events", []):
            if event.get("type") == "tool" and event["status"] == "success":
                successful_tools.add(event["tool_name"])
            if event.get("type") == "model":
                calls_finished &= (
                    event["status"] in ("success", "failed") and "elapsedMs" in event
                )
                pending = set()
                for message in event["request"]["messages"]:
                    if message.get("role") == "system":
                        content = message.get("content", "")
                        if "{" in content:
                            try:
                                context = json.loads(content[content.index("{") :])
                            except (ValueError, TypeError):
                                context = {}
                            if isinstance(context, dict):
                                integrity_warnings.update(
                                    warning
                                    for warning in context.get("warnings", [])
                                    if "哈希" in warning or "身份" in warning
                                )
                    if message.get("tool_calls"):
                        protocol_valid &= not pending
                        pending.update(call["id"] for call in message["tool_calls"])
                    elif message["role"] == "tool":
                        protocol_valid &= message.get("tool_call_id") in pending
                        pending.discard(message.get("tool_call_id"))
                    else:
                        protocol_valid &= not pending
                protocol_valid &= not pending
    check(
        "每轮八工具真实成功覆盖",
        successful_tools == EXPECTED_TOOLS,
        sorted(successful_tools),
    )
    check("模型与工具协议关联完整", protocol_valid)
    check("全部模型调用有结局和耗时", calls_finished)
    check(
        "真实详情与索引身份哈希一致", not integrity_warnings, sorted(integrity_warnings)
    )
    for report_id in flow.state["reports"]:
        reports = flow.request(
            "report-read",
            "GET",
            f"/api/v1/projects/{flow.state['projectId']}/reports/{report_id}",
        )
        check("报告重读成功", bool(reports))
        valid = True
        for evidence in reports[0]["evidence"]:
            if evidence["sourceType"] != "source_file":
                continue
            source = flow.output / "源文件副本" / evidence["logicalPath"]
            lines = source.read_text(encoding="utf-8").splitlines()
            expected = "\n".join(
                f"{index}: {lines[index - 1]}"
                for index in range(evidence["startLine"], evidence["endLine"] + 1)
            )
            valid &= (
                evidence["text"] == expected
                and evidence["contentHash"]
                == __import__("hashlib").sha256(source.read_bytes()).hexdigest()
            )
        check("报告原文证据逐行可定位", valid)
    failed = [item["name"] for item in results if not item["passed"]]
    flow.state["automatedPassed"] = not failed
    flow.checkpoint()
    save(flow.output / "测试结果" / "确定性验收.json", results)
    summary = [
        "# 本轮验收汇总",
        "",
        f"项目：{flow.state['projectId']}；会话：{flow.state['conversationId']}",
        "",
        f"自动检查：{len(results) - len(failed)}/{len(results)} 通过。",
        "",
        "报告事实质量仍须按基准逐项审阅，重启恢复须在显式重启后重新执行 verify。",
        "",
        *[
            f"- {'通过' if item['passed'] else '失败'}：{item['name']}"
            for item in results
        ],
    ]
    (flow.output / "本轮汇总.md").write_text("\n".join(summary), encoding="utf-8")
    if failed:
        raise ValueError("验收未通过：" + "、".join(failed))
