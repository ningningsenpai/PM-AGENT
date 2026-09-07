"""模拟前端职责的分阶段闭环脚本，保留失败现场与续跑检查点。"""

from __future__ import annotations

from cli import ChineseArgumentParser
import hashlib
import json
import mimetypes
import shutil
import sqlite3
from uuid import uuid4

from client import FlowClient, data, save
from environment import ROOT, configure

STAGES = (
    "setup",
    "plan",
    "upload",
    "update",
    "parse",
    "status",
    "conversation",
    "tools",
    "tool-cases",
    "learn",
    "reports",
    "correct",
    "verify",
)


class Flow:
    def __init__(self, campaign, round_id):
        self.campaign = configure(campaign)
        self.output = self.campaign / round_id
        self.output.mkdir(parents=True, exist_ok=True)
        self.state_file = self.output / "状态检查点.json"
        self.state = (
            json.loads(self.state_file.read_text(encoding="utf-8"))
            if self.state_file.exists()
            else {"stages": [], "runs": []}
        )
        self.client = FlowClient(self.output)
        self.credentials = self.output / ".credentials.local"
        if self.credentials.exists():
            self.client.token = json.loads(
                self.credentials.read_text(encoding="utf-8")
            )["token"]

    def checkpoint(self):
        save(self.state_file, self.state)

    def request(self, label, method, path, **kwargs):
        return data(self.client.send(label, method, path, **kwargs))

    @property
    def files_url(self):
        return f"/api/v1/projects/{self.state['projectId']}/files"

    @property
    def conversation_url(self):
        return f"/api/v1/agent/conversations/{self.state['conversationId']}"

    def run_result(self, label, result):
        if result.get("runId"):
            self.state["runs"].append({"label": label, "id": result["runId"]})
            save(self.output / "模型与工具轨迹" / f"{result['runId']}.json", result)
            self.checkpoint()
        if result.get("status") != "success":
            raise ValueError(f"{label} 运行未成功：{result.get('error')}")
        return result.get("result", {})

    def ask(self, label, text):
        return self.run_result(
            label,
            self.request(
                label,
                "POST",
                self.conversation_url + "/messages",
                json={"content": text},
            ),
        )

    def setup(self):
        marker = uuid4().hex[:12]
        login = {
            "username": f"验收-{marker}",
            "email": f"flow-{marker}@example.test",
            "password": f"Flow-{uuid4().hex}!",
        }
        self.request("register", "POST", "/api/v1/auth/register", json=login)
        authenticated = self.request(
            "login",
            "POST",
            "/api/v1/auth/login",
            json={"email": login["email"], "password": login["password"]},
        )
        self.client.token = authenticated["tokenValue"]
        save(self.credentials, {"token": self.client.token, "login": login})
        self.state["userId"] = authenticated["user"]["id"]
        project = self.request(
            "create-project",
            "POST",
            "/api/v1/projects",
            json={"projectName": f"星河工单台-{marker}"},
        )
        self.state["projectId"] = project["id"]
        other = self.request(
            "create-other-project",
            "POST",
            "/api/v1/projects",
            json={"projectName": f"隔离项目-{marker}"},
        )
        self.state["otherProjectId"] = other["id"]
        shutil.copytree(
            ROOT / "fixtures", self.output / "源文件副本", dirs_exist_ok=True
        )
        source = self.output / "源文件副本"
        with (source / "app/api.py").open("a", encoding="utf-8") as stream:
            stream.write("\n# 同步测试的中间版本。\n")
        (source / "obsolete.md").write_text(
            "本文件用于验证同步删除，不参与解析。", encoding="utf-8"
        )
        self.checkpoint()

    def plan(self):
        source = self.output / "源文件副本"
        items = []
        for file in sorted(source.rglob("*")):
            if file.is_file():
                raw = file.read_bytes()
                items.append(
                    {
                        "relativePath": file.relative_to(source).as_posix(),
                        "sizeBytes": len(raw),
                        "sourceMtimeMs": int(file.stat().st_mtime * 1000),
                        "contentHash": hashlib.sha256(raw).hexdigest(),
                        "contentType": mimetypes.guess_type(file.name)[0]
                        or "text/plain",
                    }
                )
        self.state["plan"] = self.request(
            "plan",
            "POST",
            self.files_url + "/sync/plan",
            json={"snapshotComplete": True, "scope": "project", "items": items},
        )
        save(self.output / "数据快照" / f"plan-{uuid4().hex}.json", self.state["plan"])

    def upload_item(self, item, update=False):
        file = self.output / "源文件副本" / item["relativePath"]
        form = {"sourceMtimeMs": str(item["sourceMtimeMs"])}
        if update:
            form["lockVersion"] = str(item["lockVersion"])
        else:
            form["relativePath"] = item["relativePath"]
        with file.open("rb") as stream:
            self.request(
                "update-content" if update else "upload",
                "PUT" if update else "POST",
                self.files_url + (f"/{item['remoteFileId']}/content" if update else ""),
                data=form,
                files={"file": (file.name, stream, item["contentType"])},
            )

    def upload(self):
        for item in self.state["plan"]["added"]:
            self.upload_item(item)

    def update(self):
        source = self.output / "源文件副本"
        shutil.copyfile(ROOT / "fixtures/app/api.py", source / "app/api.py")
        (source / "obsolete.md").unlink(missing_ok=True)
        self.plan()
        for item in self.state["plan"]["modified"]:
            self.upload_item(item, update=True)
        for item in self.state["plan"]["deleted"]:
            self.request(
                "delete",
                "DELETE",
                self.files_url + f"/{item['remoteFileId']}",
                params={"lockVersion": item["lockVersion"]},
            )

    def parse(self):
        result = self.request(
            "parse", "POST", self.files_url + "/parse/init", params={"force": False}
        )
        self.state["parse"] = result
        if result.get("runId"):
            trace = self.request(
                "parse-trace", "GET", f"/api/v1/agent/runs/{result['runId']}"
            )
            self.run_result("parse", trace)

    def status(self):
        files = self.request("status", "GET", self.files_url)
        self.state["files"] = files
        save(self.output / "数据快照" / f"files-{uuid4().hex}.json", files)

    def conversation(self):
        conversation = self.request(
            "conversation",
            "POST",
            "/api/v1/agent/conversations",
            json={"projectId": self.state["projectId"]},
        )
        self.state["conversationId"] = conversation["id"]

    def tools(self):
        self.state["tools"] = self.request(
            "tools",
            "GET",
            "/api/v1/agent/tools",
            params={"conversationId": self.state["conversationId"]},
        )

    def tool_cases(self):
        cases = [
            (
                "get_current_project",
                "请实际调用 get_current_project，告诉我当前项目名称和状态。",
            ),
            (
                "list_owned_projects",
                "请实际调用 list_owned_projects，列出我拥有的项目。",
            ),
            (
                "list_current_project_files",
                "请实际调用 list_current_project_files，核对当前项目的文件数与解析状态。",
            ),
            (
                "retrieve_project_context",
                "请实际调用 retrieve_project_context 检索当前项目开发阶段、已实现能力和风险，不要仅依赖历史回答。",
            ),
        ]
        for name, prompt in cases:
            self.ask(name, prompt)
        self.ask(
            "learning-input",
            "请记住以下信息：我在所有项目中偏好简洁中文，先列结论再列依据。在所有项目中把“小星”归一化为“星河工单台”。确认本项目预计上线日期为 2026 年 10 月 1 日；本周短期事项是补充新增接口测试。只确认收到，实际学习稍后由我点击 learn。",
        )

    def learn(self):
        self.run_result(
            "learn", self.request("learn", "POST", self.conversation_url + "/learn")
        )
        self.state["entriesBefore"] = self.request(
            "entries",
            "GET",
            "/api/v1/agent/context-entries",
            params={"projectId": self.state["projectId"]},
        )
        self.ask(
            "list_context_entries",
            "请实际调用 list_context_entries，列出当前有效的词条、习惯和项目记忆，附来源版本。",
        )

    def reports(self):
        self.state["reports"] = []
        for kind in ("development", "risk"):
            result = self.run_result(
                f"report-{kind}",
                self.request(
                    f"report-{kind}",
                    "POST",
                    f"/api/v1/projects/{self.state['projectId']}/reports",
                    json={"kind": kind},
                ),
            )
            report = result["report"]
            self.state["reports"].append(report["id"])
            (self.output / "报告").mkdir(exist_ok=True)
            (self.output / "报告" / f"{report['id']}-{kind}.md").write_text(
                report["markdown"], encoding="utf-8"
            )
        self.ask(
            "get_project_report",
            "请实际调用 get_project_report 读取最新风险报告，说明生成时间及主要结论。",
        )
        file_id = next(
            file["id"]
            for file in self.state["files"]
            if file["relativePath"] == "app/repository.py"
        )
        self.ask(
            "read_project_file_evidence",
            f"请实际调用 read_project_file_evidence，读取文件 {file_id} 的第 1 至 15 行，核实查询和新增的 SQL 安全性差异。",
        )

    def correct(self):
        self.ask(
            "correction-input",
            "更正此前本项目上线日期：由 2026 年 10 月 1 日改为 2026 年 10 月 8 日。这是最新确认决策；仓库文档尚未修改。其他习惯和词条保持不变。只确认收到，随后我点击 learn。",
        )
        self.run_result(
            "learn-correction",
            self.request("learn-correction", "POST", self.conversation_url + "/learn"),
        )
        self.state["entriesAfter"] = self.request(
            "entries-after",
            "GET",
            "/api/v1/agent/context-entries",
            params={"projectId": self.state["projectId"]},
        )
        self.ask(
            "get_context_changes",
            "请实际调用 get_context_changes，核对上线日期纠正前后的内容、版本与对应用户消息。",
        )
        self.state["finalAnswer"] = self.ask(
            "final-answer",
            "小星现在最新确认的上线日期是什么？请使用最新有效记忆核实，并区分文档原日期和用户最新决策。",
        )

    def verify(self):
        from verify import verify_round

        verify_round(self)

    def trace(self):
        for run in self.state["runs"]:
            trace = self.request("trace", "GET", f"/api/v1/agent/runs/{run['id']}")
            save(self.output / "模型与工具轨迹" / f"{run['id']}.json", trace)


def main():
    parser = ChineseArgumentParser(description="助手闭环 HTTP 调试和每轮归档")
    parser.add_argument("stage", choices=[*STAGES, "all", "trace", "retry"])
    parser.add_argument("--campaign", default="mvp-20260908")
    parser.add_argument("--round", default="round-001")
    parser.add_argument("--file-ids", help="retry 时指定逗号分隔的文件 ID")
    args = parser.parse_args()
    if not args.round.startswith("round-") or not args.round[6:].isdigit():
        raise ValueError("轮次必须为 round-数字")
    flow = Flow(args.campaign, args.round)
    from version import capture_version

    capture_version(flow)
    stages = STAGES if args.stage == "all" else (args.stage,)
    try:
        for stage in stages:
            if args.stage == "all" and stage in flow.state["stages"]:
                continue
            if stage == "retry":
                ids = [int(item) for item in (args.file_ids or "").split(",") if item]
                if not ids:
                    raise ValueError("定向重试必须通过 --file-ids 指定文件")
                result = flow.request(
                    "retry",
                    "POST",
                    flow.files_url + "/parse/init",
                    params={"force": True},
                    json={"fileIds": ids},
                )
                flow.state["retry"] = result
            else:
                getattr(flow, stage.replace("-", "_"))()
            if stage not in flow.state["stages"]:
                flow.state["stages"].append(stage)
            flow.checkpoint()
    except Exception as exc:
        flow.state["lastError"] = str(exc)
        flow.checkpoint()
        (flow.output / "本轮汇总.md").write_text(
            f"# 本轮尚未通过\n\n完成阶段：{flow.state['stages']}\n\n失败：{exc}\n\n原始记录与状态已保留；修复后续跑或开启新轮次。\n",
            encoding="utf-8",
        )
        raise
    finally:
        flow.client.http.close()
        ledger = flow.campaign / "费用账本.sqlite"
        if ledger.exists():
            with sqlite3.connect(ledger) as connection:
                calls = [
                    dict(zip(("callId", "reservedCny", "accountedCny", "state"), row))
                    for row in connection.execute(
                        "SELECT id,reserved,charged,state FROM calls"
                    )
                ]
            (flow.campaign / "费用记录.jsonl").write_text(
                "\n".join(json.dumps(row, ensure_ascii=False) for row in calls) + "\n",
                encoding="utf-8",
            )
            print(
                f"累计保守记账：{sum(row['accountedCny'] for row in calls):.6f} 元 / 30 元",
                flush=True,
            )


if __name__ == "__main__":
    main()
