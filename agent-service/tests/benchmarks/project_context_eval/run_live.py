"""通过真实 API 上传版本快照，并可选执行解析和 50 题回答。"""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx

from .dataset import dataset_sha256, load_dataset
from .fixture import ROOT, materialize, text_files


def _save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class LiveRun:
    """保留本地可恢复状态和脱敏 HTTP 证据。"""

    def __init__(self, base_url: str, output: Path) -> None:
        safe_root = (ROOT / "output").resolve()
        self.output = output.resolve()
        if not self.output.is_relative_to(safe_root):
            raise ValueError(f"结果目录必须位于 {safe_root} 内")
        if self.output.exists() and any(self.output.iterdir()):
            raise ValueError(f"结果目录必须为空：{self.output}")
        self.output.mkdir(parents=True, exist_ok=True)
        self.http = httpx.Client(base_url=base_url, timeout=600)
        self.token = ""
        self.state: dict = {
            "schemaVersion": "1.0",
            "startedAt": datetime.now(UTC).isoformat(),
            "baseUrl": base_url,
            "datasetSha256": dataset_sha256(),
            "versions": {},
        }

    def close(self) -> None:
        self.http.close()

    def _persist_state(self) -> None:
        _save_json(self.output / "local-resume.json", self.state)

    def request(self, label: str, method: str, path: str, **kwargs):
        headers = dict(kwargs.pop("headers", {}))
        headers.setdefault("X-Trace-Id", f"project-eval-{label}-{uuid4().hex}")
        headers.setdefault("X-Idempotency-Key", f"project-eval-{label}-{uuid4().hex}")
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        started = time.perf_counter()
        response = self.http.request(method, path, headers=headers, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = {"message": response.text[:1000]}
        record = {
            "label": label,
            "method": method,
            "path": path,
            "httpStatus": response.status_code,
            "elapsedMs": round((time.perf_counter() - started) * 1000, 3),
            "response": body,
        }
        raw = json.dumps(record, ensure_ascii=False)
        for secret in (self.token, self.state.get("password", "")):
            if secret:
                raw = raw.replace(secret, "[已隐藏]")
        _save_json(
            self.output / "requests" / f"{label}-{uuid4().hex[:8]}.json",
            json.loads(raw),
        )
        if response.status_code >= 400 or body.get("code") != 200:
            raise RuntimeError(
                f"{label} 请求失败：HTTP {response.status_code}，{body.get('message')}"
            )
        return body.get("data")

    def setup_account(self) -> None:
        marker = uuid4().hex[:12]
        email = f"project-eval-{marker}@example.test"
        password = f"Eval-{uuid4().hex}!"
        self.request(
            "register",
            "POST",
            "/api/v1/auth/register",
            json={"username": f"评测用户-{marker}", "email": email, "password": password},
        )
        login = self.request(
            "login",
            "POST",
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        self.token = login["tokenValue"]
        self.state.update(
            {
                "email": email,
                "password": password,
                "userId": str(login["user"]["id"]),
            }
        )
        self._persist_state()

    def setup_version(self, version: str) -> None:
        fixture = materialize(version, self.output / "fixtures" / version)
        project = self.request(
            f"create-project-{version}",
            "POST",
            "/api/v1/projects",
            json={"projectName": f"学生管理冻结评测-{version}-{uuid4().hex[:6]}"},
        )
        project_id = int(project["id"])
        uploaded = []
        skipped = []
        for relative_path, content in text_files(fixture.root).items():
            if relative_path == ".gitignore":
                skipped.append({"path": relative_path, "reason": "命中业务上传忽略规则"})
                continue
            content_type = mimetypes.guess_type(relative_path)[0] or "text/plain"
            data = self.request(
                f"upload-{version}",
                "POST",
                f"/api/v1/projects/{project_id}/files",
                headers={"X-Idempotency-Key": uuid4().hex},
                data={
                    "relativePath": relative_path,
                    "sourceMtimeMs": str(time.time_ns() // 1_000_000),
                },
                files={
                    "file": (
                        Path(relative_path).name,
                        content.encode("utf-8"),
                        content_type,
                    )
                },
            )
            uploaded.append(
                {
                    "id": str(data["fileId"]),
                    "path": relative_path,
                    "contentHash": data.get("contentHash"),
                }
            )
        self.state["versions"][version] = {
            "projectId": str(project_id),
            "fixtureManifest": fixture.manifest,
            "uploaded": uploaded,
            "skipped": skipped,
            "parse": None,
            "conversationIds": {},
        }
        self._persist_state()

    def parse_version(self, version: str) -> None:
        version_state = self.state["versions"][version]
        project_id = int(version_state["projectId"])
        result = self.request(
            f"parse-{version}",
            "POST",
            f"/api/v1/projects/{project_id}/files/parse/init",
        )
        version_state["parse"] = result
        self._persist_state()

    def ask_questions(self, version: str, questions) -> None:
        version_state = self.state["versions"][version]
        project_id = int(version_state["projectId"])
        answer_path = self.output / "answers.jsonl"
        for index, question in enumerate(questions, 1):
            conversation = self.request(
                f"conversation-{question.id}",
                "POST",
                "/api/v1/agent/conversations",
                json={"projectId": str(project_id), "title": f"冻结评测 {question.id}"},
            )
            conversation_id = int(conversation["id"])
            version_state["conversationIds"][question.id] = str(conversation_id)
            self._persist_state()
            started = time.perf_counter()
            result = self.request(
                f"answer-{question.id}",
                "POST",
                f"/api/v1/agent/conversations/{conversation_id}/messages",
                json={"content": question.question},
            )
            record = {
                "questionId": question.id,
                "version": version,
                "split": question.split,
                "category": question.category,
                "latencyMs": round((time.perf_counter() - started) * 1000, 3),
                "result": result,
            }
            with answer_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"[{version} {index:02d}/{len(questions):02d}] {question.id} 回答完成", flush=True)


def run(
    base_url: str,
    output: Path,
    *,
    parse: bool,
    ask: bool,
    allow_external_model_data: bool,
) -> int:
    if (parse or ask) and not allow_external_model_data:
        raise ValueError("解析或回答会发送脱敏测试代码到外部模型，必须显式传入 --allow-external-model-data")
    if ask and not parse:
        raise ValueError("回答阶段要求同一次运行先完成解析")
    questions, _ = load_dataset()
    live = LiveRun(base_url, output)
    try:
        health = live.http.get("/internal/health")
        if health.status_code != 200:
            raise RuntimeError("后端健康检查未通过")
        live.setup_account()
        for version in ("v1", "v2", "v3"):
            live.setup_version(version)
            if parse:
                live.parse_version(version)
            if ask:
                live.ask_questions(
                    version,
                    [item for item in questions if item.version == version],
                )
        live.state["finishedAt"] = datetime.now(UTC).isoformat()
        live.state["completed"] = True
        live._persist_state()
        print(f"真实 API 运行完成：{output}")
        return 0
    except Exception as exception:
        live.state["failure"] = {
            "type": type(exception).__name__,
            "message": str(exception),
        }
        live._persist_state()
        raise
    finally:
        live.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="执行版本化项目的真实 API 上传、解析和回答")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--parse", action="store_true")
    parser.add_argument("--ask", action="store_true")
    parser.add_argument("--allow-external-model-data", action="store_true")
    args = parser.parse_args()
    return run(
        args.base_url,
        args.output.resolve(),
        parse=args.parse,
        ask=args.ask,
        allow_external_model_data=args.allow_external_model_data,
    )


if __name__ == "__main__":
    raise SystemExit(main())
