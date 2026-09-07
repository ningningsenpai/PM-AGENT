"""记录源码、Prompt 及非敏感运行配置，识别混用版本的调试轮次。"""

import hashlib
import json
import subprocess
from uuid import uuid4

from client import save
from environment import REPO, ROOT, SERVICE


def capture_version(flow):
    from app.core.config import get_settings

    settings = get_settings().llm
    llm = settings.get_llm_config("deepseek")
    config = {
        "model": llm.model,
        "context": llm.context_window_tokens,
        "reservedOutput": llm.reserved_output_tokens,
        "chatMaxOutput": settings.chat_max_tokens,
        "learningMaxOutput": settings.memory_max_tokens,
        "reportMaxOutput": settings.report_max_tokens,
        "fileMaxOutput": settings.file_detail.max_output_tokens,
        "fileTimeout": settings.file_detail.request_timeout_seconds,
        "requestTimeout": llm.extra.get("timeout_seconds"),
        "fileEnabled": settings.file_detail.enabled,
    }
    paths = sorted(
        {
            *list((SERVICE / "app").rglob("*.py")),
            *list((SERVICE / "migrations").rglob("*.py")),
            *list(ROOT.glob("*.py")),
            *[
                path
                for path in (ROOT / "fixtures").rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            ],
        }
    )
    fingerprints = {
        path.relative_to(REPO).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }
    digest = hashlib.sha256(
        json.dumps({"files": fingerprints, "config": config}, sort_keys=True).encode()
    ).hexdigest()
    current = {
        "commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True
        ).strip(),
        "codeAndConfigFingerprint": digest,
        "config": config,
        "files": fingerprints,
        "promptVersions": {
            "learning": "learn-v1",
            "report": "report-v1",
            "fileDetail": fingerprints.get(
                "agent-service/app/project_context/file_detail/service.py"
            ),
        },
    }
    baseline = flow.output / "版本与配置.json"
    if baseline.exists():
        previous = json.loads(baseline.read_text(encoding="utf-8"))
        if previous["codeAndConfigFingerprint"] != digest:
            flow.state["mixedVersions"] = True
    else:
        save(baseline, current)
    save(flow.output / "版本记录" / f"{uuid4().hex}.json", current)
    flow.checkpoint()
