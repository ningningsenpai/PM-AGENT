"""通过真实 HTTP 调用项目文件接口，并保存调试记录。"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import BinaryIO
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


class ProjectFileClient:
    """只调用项目文件公开接口；HTTP 和业务错误响应均作为观察数据保留。"""

    def __init__(self, http: httpx.Client, config: dict, output_dir: Path) -> None:
        self.http = http
        self.config = config
        self.output_dir = output_dir
        self.base_url = (
            f"{config['baseUrl']}/api/v1/projects/{config['projectId']}/files"
        )
        (output_dir / "requests").mkdir(parents=True, exist_ok=True)

    def save_record(self, record: dict) -> dict:
        record["recordId"] = uuid4().hex
        record["recordedAt"] = datetime.now(timezone.utc).isoformat()
        text = json.dumps(record, ensure_ascii=False, indent=2)
        # 后端或代理若回显令牌，也不把认证信息写入本地记录。
        escaped_token = json.dumps(self.config["accessToken"], ensure_ascii=False)[1:-1]
        text = text.replace(escaped_token, "[已隐藏]")
        record = json.loads(text)
        stage = record["stage"]
        name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        history = (
            self.output_dir / "requests" / f"{name}-{stage}-{record['recordId']}.json"
        )
        write_json(history, record)
        if stage in {"upload", "update"}:
            with (self.output_dir / f"{stage}s.jsonl").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        else:
            write_json(self.output_dir / f"{stage}.response.json", record)
        print(text, flush=True)
        print(f"调用记录：{history}", flush=True)
        return record

    def send(
        self,
        stage: str,
        method: str,
        path: str = "",
        *,
        headers: dict | None = None,
        file_info: dict | None = None,
        timeout: float | None = 120,
        **kwargs,
    ) -> dict:
        trace_id = f"file-flow-{stage}-{uuid4().hex}"
        request_headers = {"X-Trace-Id": trace_id, **(headers or {})}
        record = {
            "stage": stage,
            "request": {
                "method": method,
                "url": self.base_url + path,
                "headers": {**request_headers, "Authorization": "Bearer [已隐藏]"},
                "params": kwargs.get("params"),
                "json": kwargs.get("json"),
                "form": kwargs.get("data"),
                "file": file_info,
            },
            "response": None,
            "error": None,
        }
        print(
            f"开始调用：{stage} {method} {self.base_url + path}，追踪 ID：{trace_id}",
            flush=True,
        )
        started = perf_counter()
        try:
            response = self.http.request(
                method,
                self.base_url + path,
                headers={
                    **request_headers,
                    "Authorization": f"Bearer {self.config['accessToken']}",
                },
                timeout=timeout,
                **kwargs,
            )
            try:
                body = response.json()
            except ValueError:
                body = response.text
            record["response"] = {
                "status": response.status_code,
                "contentType": response.headers.get("content-type"),
                "traceId": response.headers.get("x-trace-id"),
                "body": body,
            }
        except httpx.RequestError as error:
            record["error"] = (
                f"网络请求未完成（{type(error).__name__}），请查看服务端日志"
            )
        except KeyboardInterrupt:
            record["error"] = "用户中断请求；服务端可能仍在处理，请查看服务端日志"
            raise
        finally:
            record["elapsedMs"] = round((perf_counter() - started) * 1000, 2)
            saved = self.save_record(record)
        return saved

    def plan(self, manifest: dict) -> dict:
        return self.send("plan", "POST", "/sync/plan", json=manifest)

    @contextmanager
    def _open_planned_file(self, item: dict) -> Iterator[BinaryIO]:
        """内容覆盖与路径更新都以规划时的本地快照为准。"""
        path = Path(item["localPath"])
        if not path.resolve().is_relative_to(Path(self.config["sourceDir"])):
            raise ValueError("文件不在本轮测试目录内")
        with path.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if (
                stat.st_size != item["sizeBytes"]
                or stat.st_mtime_ns // 1_000_000 != item["sourceMtimeMs"]
                or digest != item["contentHash"]
            ):
                raise ValueError("文件在规划后发生变化，请重新执行 plan")
            stream.seek(0)
            yield stream

    def upload(self, item: dict) -> dict:
        """发送本轮清单对应的文件，文件已变化时留记录并跳过。"""
        path = Path(item["localPath"])
        try:
            with self._open_planned_file(item) as stream:
                identity = json.dumps(
                    [
                        self.config["projectId"],
                        self.config["runId"],
                        item["relativePath"],
                        item["contentHash"],
                    ],
                    ensure_ascii=False,
                )
                key = f"file-flow-{uuid5(NAMESPACE_URL, identity).hex}"
                return self.send(
                    "upload",
                    "POST",
                    headers={"X-Idempotency-Key": key},
                    data={
                        "relativePath": item["relativePath"],
                        "sourceMtimeMs": str(item["sourceMtimeMs"]),
                    },
                    files={"file": (path.name, stream, item["contentType"])},
                    file_info=item,
                )
        except (OSError, ValueError) as error:
            message = (
                str(error) if isinstance(error, ValueError) else "无法读取本地文件"
            )
            return self.save_record(
                {
                    "stage": "upload",
                    "request": {"file": item},
                    "response": None,
                    "error": message,
                }
            )

    def update(self, item: dict, planned_item: dict, change: str) -> dict:
        """更新已有项目文件；路径变化只发送元数据，内容变化发送原始字节。"""
        file_id = planned_item["remoteFileId"]
        lock_version = planned_item["lockVersion"]
        metadata = {
            "sourceMtimeMs": item["sourceMtimeMs"],
            "lockVersion": lock_version,
        }
        file_info = {**item, "change": change, "plannedItem": planned_item}
        try:
            with self._open_planned_file(item) as stream:
                if change == "moved":
                    return self.send(
                        "update",
                        "PATCH",
                        f"/{file_id}/path",
                        json={"relativePath": item["relativePath"], **metadata},
                        file_info=file_info,
                    )
                identity = json.dumps(
                    [
                        "content",
                        self.config["projectId"],
                        self.config["runId"],
                        file_id,
                        lock_version,
                        item["contentHash"],
                        item["sourceMtimeMs"],
                    ],
                    ensure_ascii=False,
                )
                key = f"file-flow-{uuid5(NAMESPACE_URL, identity).hex}"
                return self.send(
                    "update",
                    "PUT",
                    f"/{file_id}/content",
                    headers={"X-Idempotency-Key": key},
                    data={name: str(value) for name, value in metadata.items()},
                    files={
                        "file": (
                            Path(item["localPath"]).name,
                            stream,
                            item["contentType"],
                        )
                    },
                    file_info=file_info,
                )
        except (OSError, ValueError) as error:
            message = (
                str(error) if isinstance(error, ValueError) else "无法读取本地文件"
            )
            return self.save_record(
                {
                    "stage": "update",
                    "request": {"file": file_info},
                    "response": None,
                    "error": message,
                }
            )

    def delete(self, planned_item: dict) -> dict:
        """删除项只依赖远端规划元数据，不读取或删除本地源文件。"""
        return self.send(
            "update",
            "DELETE",
            f"/{planned_item['remoteFileId']}",
            params={"lockVersion": planned_item["lockVersion"]},
            file_info={"change": "deleted", "plannedItem": planned_item},
        )

    def parse(self) -> dict:
        # 解析接口等待整批模型调用和产物写入完成，与前端保持相同的等待方式。
        identity = json.dumps(
            [
                "parse",
                self.config["projectId"],
                self.config["runId"],
                self.config["forceAnalysis"],
            ],
            ensure_ascii=False,
        )
        key = f"file-flow-{uuid5(NAMESPACE_URL, identity).hex}"
        return self.send(
            "parse",
            "POST",
            "/parse/init",
            headers={"X-Idempotency-Key": key},
            params={"force": str(self.config["forceAnalysis"]).lower()},
            timeout=None,
        )

    def files(self) -> dict:
        return self.send("files", "GET", params={"businessCode": "project"})
