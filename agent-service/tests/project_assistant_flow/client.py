"""只通过 HTTP 调试接口，每次请求独立归档，令牌不进入记录。"""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class FlowClient:
    def __init__(self, output):
        self.output = output
        self.http = httpx.Client(
            base_url="http://127.0.0.1:18080", timeout=1800, trust_env=False
        )
        self.token = ""

    def send(self, label, method, url, *, key=None, **kwargs):
        trace = f"assistant-{label}-{uuid4().hex}"
        headers = {"X-Trace-Id": trace, "X-Idempotency-Key": key or uuid4().hex}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        record = {
            "label": label,
            "traceId": trace,
            "request": {
                "method": method,
                "url": url,
                "json": kwargs.get("json"),
                "params": kwargs.get("params"),
                "form": kwargs.get("data"),
            },
            "startedAt": datetime.now(UTC).isoformat(),
        }
        if (
            isinstance(record["request"]["json"], dict)
            and "password" in record["request"]["json"]
        ):
            record["request"]["json"] = {
                **record["request"]["json"],
                "password": "[已隐藏]",
            }
        started = time.perf_counter()
        try:
            response = self.http.request(method, url, headers=headers, **kwargs)
            record["httpStatus"] = response.status_code
            body = response.json()
            record["response"] = body
            record["elapsedMs"] = round((time.perf_counter() - started) * 1000, 2)
            raw = json.dumps(record, ensure_ascii=False)
            returned_token = (
                (body.get("data") or {}).get("tokenValue")
                if isinstance(body.get("data"), dict)
                else None
            )
            for secret in (self.token, returned_token):
                if secret:
                    raw = raw.replace(secret, "[已隐藏]")
            save(self.output / "请求记录" / f"{trace}.json", json.loads(raw))
            print(
                f"{label}：HTTP {response.status_code}，业务码 {body.get('code')}，{record['elapsedMs']} ms",
                flush=True,
            )
            return body
        except Exception as exc:
            record["error"] = type(exc).__name__
            record["elapsedMs"] = round((time.perf_counter() - started) * 1000, 2)
            save(self.output / "请求记录" / f"{trace}.json", record)
            raise


def data(body):
    if body.get("code") != 200:
        raise ValueError(f"流程依赖的接口失败：{body.get('message')}")
    return body["data"]
