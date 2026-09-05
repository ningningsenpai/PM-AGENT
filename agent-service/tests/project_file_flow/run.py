"""项目文件流程调试入口，支持分阶段观察请求与响应。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import httpx
from client import ProjectFileClient, write_json
from manifest import build_manifest

SCRIPT_DIR = Path(__file__).resolve().parent
SERVICE_DIR = SCRIPT_DIR.parents[1]
DEFAULT_ENV_FILE = SERVICE_DIR / "test_client" / "http-client.env.json"
STAGES = ("plan", "upload", "update", "parse", "files", "all")


class FlowArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return super().format_help().replace("usage:", "用法:", 1)

    def error(self, message: str) -> None:
        raise ValueError("命令行参数无效，请使用 --help 查看阶段和配置文件参数")


def read_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as error:
        raise ValueError(f"无法读取文件：{path}") from error
    except ValueError as error:
        raise ValueError(f"文件不是有效的 JSON：{path}") from error
    if not isinstance(value, dict):
        raise TypeError(f"文件内容必须为 JSON 对象：{path}")
    return value


def load_config(env_file: Path) -> dict:
    config = read_json(env_file).get("project_file")
    if not isinstance(config, dict):
        raise TypeError("环境文件缺少 project_file 对象")
    config = dict(config)
    for key in ("baseUrl", "accessToken", "projectId", "runId", "sourceDir"):
        value = config.get(key)
        if value is None or not str(value).strip():
            raise ValueError(f"请填写 project_file.{key}")
        config[key] = str(value).strip()
    config["baseUrl"] = config["baseUrl"].rstrip("/")
    url = httpx.URL(config["baseUrl"])
    if (
        url.scheme not in {"http", "https"}
        or not url.host
        or url.userinfo
        or url.query
        or url.fragment
    ):
        raise ValueError(
            "baseUrl 必须是有效的 HTTP 服务地址，不能包含凭据、查询参数或片段"
        )
    if not re.fullmatch(r"[1-9][0-9]*", config["projectId"]):
        raise ValueError("projectId 必须是正整数 ID")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", config["runId"]):
        raise ValueError(
            "runId 须为 1 至 80 位字母、数字、下划线或短横线，并以字母或数字开头"
        )
    config.setdefault("forceAnalysis", False)
    if not isinstance(config["forceAnalysis"], bool):
        raise TypeError("forceAnalysis 必须为 JSON 布尔值 true 或 false")
    source = Path(config["sourceDir"])
    if not source.is_absolute():
        source = env_file.resolve().parent / source
    config["sourceDir"] = str(source.resolve())
    return config


def context(config: dict) -> dict:
    return {key: config[key] for key in ("baseUrl", "projectId", "runId", "sourceDir")}


def plan_stage(client: ProjectFileClient) -> None:
    snapshot = {
        "context": context(client.config),
        **build_manifest(Path(client.config["sourceDir"])),
    }
    write_json(client.output_dir / "manifest.json", snapshot)
    print(
        f"本地清单：{len(snapshot['files'])} 个候选文件，{len(snapshot['localRejections'])} 个拒绝项"
    )
    for item in snapshot["localRejections"]:
        print(f"本地过滤：{item['relativePath']}，原因：{item['reason']}")
    client.plan(snapshot["request"])


def load_plan(client: ProjectFileClient) -> tuple[dict, dict]:
    """确认本地清单与规划来自同一轮，避免按过期上下文写入文件。"""
    snapshot = read_json(client.output_dir / "manifest.json")
    plan = read_json(client.output_dir / "plan.response.json")
    if snapshot.get("context") != context(client.config):
        raise ValueError("清单对应的项目、服务地址或测试目录已变化，请重新执行 plan")
    if plan.get("request", {}).get("json") != snapshot.get("request"):
        raise ValueError("规划响应与本地清单不对应，请重新执行 plan")
    if plan.get("request", {}).get("url") != client.base_url + "/sync/plan":
        raise ValueError("规划响应对应的项目或服务地址已变化，请重新执行 plan")
    response = plan.get("response") or {}
    body = response.get("body")
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise TypeError("规划响应缺少 data，无法继续，请查看 plan.response.json")
    return snapshot, data


def upload_stage(client: ProjectFileClient) -> None:
    """只读取新增项来衔接调用，不判断响应中的业务结果是否正确。"""
    snapshot, data = load_plan(client)
    added = data.get("added")
    if not isinstance(added, list):
        raise TypeError(
            "规划响应缺少 data.added，无法继续上传，请查看 plan.response.json"
        )
    print(f"本轮新增项：{len(added)} 个；其他差异分类保留在规划响应中")
    for index, planned_item in enumerate(added, start=1):
        relative_path = (
            planned_item.get("relativePath") if isinstance(planned_item, dict) else None
        )
        item = (
            snapshot["files"].get(relative_path)
            if isinstance(relative_path, str)
            else None
        )
        if item is None:
            client.save_record(
                {
                    "stage": "upload",
                    "request": {"plannedItem": planned_item},
                    "response": None,
                    "error": "新增项缺少对应的本地候选文件，已跳过",
                }
            )
            continue
        print(f"上传进度：{index}/{len(added)}，文件：{relative_path}", flush=True)
        client.upload(item)


def update_stage(client: ProjectFileClient) -> None:
    """按规划覆盖内容、更新路径及删除文件，文件 ID 和锁版本直接取自规划。"""
    snapshot, data = load_plan(client)
    for change in ("modified", "moved", "deleted"):
        if not isinstance(data.get(change), list):
            raise TypeError(
                f"规划响应缺少 data.{change}，无法继续更新，请查看 plan.response.json"
            )
    print(
        f"本轮更新项：{len(data['modified'])} 个内容变化，"
        f"{len(data['moved'])} 个路径变化，{len(data['deleted'])} 个删除项"
    )
    for change in ("modified", "moved", "deleted"):
        for index, planned_item in enumerate(data[change], start=1):
            relative_path = (
                planned_item.get(
                    "remoteRelativePath" if change == "deleted" else "relativePath"
                )
                if isinstance(planned_item, dict)
                else None
            )
            item = (
                snapshot["files"].get(relative_path)
                if isinstance(relative_path, str)
                else None
            )
            error = None
            if change != "deleted" and item is None:
                error = "更新项缺少对应的本地候选文件，已跳过"
            elif (
                not isinstance(planned_item, dict)
                or type(planned_item.get("remoteFileId")) is not int
                or planned_item["remoteFileId"] <= 0
                or type(planned_item.get("lockVersion")) is not int
                or planned_item["lockVersion"] < 0
            ):
                error = "更新项缺少有效的 remoteFileId 或 lockVersion，已跳过"
            if error:
                client.save_record(
                    {
                        "stage": "update",
                        "request": {"change": change, "plannedItem": planned_item},
                        "response": None,
                        "error": error,
                    }
                )
                continue
            print(
                f"更新进度：{change} {index}/{len(data[change])}，文件：{relative_path}",
                flush=True,
            )
            if change == "deleted":
                client.delete(planned_item)
            else:
                client.update(item, planned_item, change)


def main(argv: list[str] | None = None) -> int:
    parser = FlowArgumentParser(
        description="模拟项目文件前端流程，保存原始调用数据，不执行结果断言",
        add_help=False,
    )
    parser._positionals.title = "位置参数"
    parser._optionals.title = "可选参数"
    parser.add_argument("-h", "--help", action="help", help="显示帮助并退出")
    parser.add_argument(
        "stage",
        choices=STAGES,
        metavar="阶段",
        help="plan、upload、update、parse、files 或 all",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=DEFAULT_ENV_FILE,
        metavar="文件路径",
        help="读取其中的 project_file 环境，默认使用 test_client/http-client.env.json",
    )
    try:
        args = parser.parse_args(argv)
        config = load_config(args.env_file)
        output_dir = SCRIPT_DIR / "output" / config["projectId"] / config["runId"]
        print(f"本轮记录目录：{output_dir}", flush=True)
        with httpx.Client(trust_env=False) as http:
            client = ProjectFileClient(http, config, output_dir)
            stages = (
                ("plan", "upload", "update", "parse", "files")
                if args.stage == "all"
                else (args.stage,)
            )
            for stage in stages:
                try:
                    if stage == "plan":
                        plan_stage(client)
                    elif stage == "upload":
                        upload_stage(client)
                    elif stage == "update":
                        update_stage(client)
                    elif stage == "parse":
                        client.parse()
                    else:
                        client.files()
                except (ValueError, TypeError) as error:
                    print(f"阶段 {stage} 无法继续：{error}", file=sys.stderr)
                    return 1
        return 0
    except (OSError, ValueError, TypeError, httpx.InvalidURL) as error:
        message = (
            str(error)
            if isinstance(error, (ValueError, TypeError))
            else "本地文件操作或服务地址解析失败"
        )
        print(f"无法执行调试流程：{message}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("调试流程已由用户中断，已有记录保留在本地", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
