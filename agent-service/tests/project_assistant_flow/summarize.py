"""汇总每轮证据、调用、费用及待审阅项，保留历次汇总快照。"""

from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3


def read(path, default=None):
    return (
        json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default
    )


def summarize(output: Path):
    state = read(output / "状态检查点.json", {})
    version = read(output / "版本与配置.json", {})
    checks = read(output / "测试结果/确定性验收.json", [])
    runs = [read(path, {}) for path in (output / "模型与工具轨迹").glob("*.json")]
    models, tools = {}, []
    for run in runs:
        for event in run.get("events", []):
            if event.get("type") == "model":
                models[event["callId"]] = event
            elif event.get("type") == "tool":
                tools.append(event)
    tokens = Counter()
    for event in models.values():
        usage = (event.get("response") or {}).get("usage", {}) or {}
        for name in (
            "prompt_tokens",
            "completion_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        ):
            tokens[name] += usage.get(name, 0) or 0
    coverage = Counter(
        event["tool_name"] for event in tools if event.get("status") == "success"
    )
    failed_tools = [event for event in tools if event.get("status") != "success"]
    total = 0.0
    ledger = output.parent / "费用账本.sqlite"
    if ledger.exists():
        with sqlite3.connect(ledger) as connection:
            total = connection.execute(
                "SELECT COALESCE(SUM(charged),0) FROM calls"
            ).fetchone()[0]
    lines = [
        "# 本轮汇总",
        "",
        f"活动：{output.parent.name}；轮次：{output.name}。",
        f"源码提交：{version.get('commit', '未记录')}；配置与源码指纹：{version.get('codeAndConfigFingerprint', '未记录')}。",
        f"模型：{version.get('config', {}).get('model', '未记录')}；Prompt：{json.dumps(version.get('promptVersions', {}), ensure_ascii=False)}。",
        f"项目：{state.get('projectId', '未创建')}；会话：{state.get('conversationId', '未创建')}。",
        f"完成阶段：{' → '.join(state.get('stages', []))}。",
        f"混用版本：{'是，不可计入连续验收' if state.get('mixedVersions') else '未检测到'}。",
        "",
        "## 检查与待办",
        "",
        f"确定性检查：{sum(bool(item['passed']) for item in checks)}/{len(checks)} 通过。",
        f"当前错误：{state.get('lastError') or '无；仍须核对人工事实和恢复检查'}。",
        "人工事实审阅见 测试结果/事实审阅.md；重启恢复见 测试结果/重启恢复.json，缺失时不可判定最终通过。",
        "",
        *[
            f"- {'通过' if item['passed'] else '失败'}：{item['name']}"
            for item in checks
        ],
        "",
        "## 模型、工具与费用",
        "",
        f"模型调用：{len(models)}；失败：{sum(event.get('status') != 'success' for event in models.values())}。",
        f"输入 tokens：{tokens['prompt_tokens']}；输出 tokens：{tokens['completion_tokens']}；缓存命中输入：{tokens['prompt_cache_hit_tokens']}。",
        f"模型累计耗时：{sum(event.get('elapsedMs', 0) for event in models.values()) / 1000:.2f} 秒；工具累计耗时：{sum(event.get('duration_ms', 0) for event in tools) / 1000:.2f} 秒。",
        f"本轮已归档调用保守估算：{sum(event.get('accountedCny', event.get('reservedCny', 0)) for event in models.values()):.6f} 元；活动账本累计：{total:.6f}/30 元。估算不是服务商账单。",
        f"工具成功覆盖：{len(coverage)}/8；失败调用：{len(failed_tools)}。",
        "",
        *[f"- {name}：{count} 次成功" for name, count in sorted(coverage.items())],
        "",
        "## 运行与追踪",
        "",
        *[
            f"- {run.get('operation')}：runId={run.get('runId')}，traceId={run.get('traceId')}，状态={run.get('status')}，错误={run.get('error') or '无'}。"
            for run in runs
        ],
        "",
        "请求、工具参数和回填结果保存在 请求记录/ 与 模型与工具轨迹/；学习前后内容在状态检查点，历史版本在变更工具轨迹；证据和存储产物在 数据快照/。失败定位、修复和下一轮范围另存本轮 Markdown 记录。",
    ]
    content = "\n".join(lines) + "\n"
    (output / "本轮汇总.md").write_text(content, encoding="utf-8")
    history = output / "汇总历史"
    history.mkdir(exist_ok=True)
    (history / f"{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}.md").write_text(
        content, encoding="utf-8"
    )


if __name__ == "__main__":
    from cli import ChineseArgumentParser
    from environment import configure

    parser = ChineseArgumentParser(description="重新汇总指定测试轮次")
    parser.add_argument("--campaign", default="mvp-20260908")
    parser.add_argument("--round", required=True)
    args = parser.parse_args()
    if not args.round.startswith("round-") or not args.round[6:].isdigit():
        raise ValueError("轮次必须为 round-数字")
    summarize(configure(args.campaign) / args.round)
