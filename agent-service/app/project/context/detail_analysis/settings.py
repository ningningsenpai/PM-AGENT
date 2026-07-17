"""文件详情解析消费者配置。"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from urllib.parse import quote

from app.core.config.load_env_file import LoadConfig


@dataclass(frozen=True)
class FileDetailAnalysisSettings:
    enabled: bool
    rabbitmq_url: str
    exchange: str
    queue: str
    routing_key: str
    internal_token: str
    request_timeout_seconds: float
    max_source_bytes: int
    prefetch_count: int
    llm_enabled: bool


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_file_detail_analysis_settings() -> FileDetailAnalysisSettings:
    LoadConfig()
    username = quote(os.getenv("PM_AGENT_RABBITMQ_USERNAME", "pm-agent"), safe="")
    password = quote(os.getenv("PM_AGENT_RABBITMQ_PASSWORD", "pm-agent-dev"), safe="")
    host = os.getenv("PM_AGENT_RABBITMQ_HOST", "127.0.0.1")
    port = os.getenv("PM_AGENT_RABBITMQ_PORT", "5672")
    virtual_host = quote(os.getenv("PM_AGENT_RABBITMQ_VHOST", "pm-agent").strip("/"), safe="")
    rabbitmq_url = os.getenv(
        "PM_AGENT_RABBITMQ_URL",
        f"amqp://{username}:{password}@{host}:{port}/{virtual_host}",
    )
    return FileDetailAnalysisSettings(
        enabled=_as_bool(os.getenv("PM_AGENT_FILE_DETAIL_CONSUMER_ENABLED", "false")),
        rabbitmq_url=rabbitmq_url,
        exchange="pm-agent.project-file.events.v1",
        queue="pm-agent.file-detail.parse.v1",
        routing_key="project.file.detail.requested.v1",
        internal_token=os.getenv("PM_AGENT_INTERNAL_SERVICE_TOKEN", "pm-agent-dev-internal-token"),
        request_timeout_seconds=float(os.getenv("PM_AGENT_FILE_DETAIL_REQUEST_TIMEOUT_SECONDS", "30")),
        max_source_bytes=int(os.getenv("PM_AGENT_FILE_DETAIL_MAX_SOURCE_BYTES", str(50 * 1024 * 1024))),
        prefetch_count=int(os.getenv("PM_AGENT_FILE_DETAIL_PREFETCH_COUNT", "4")),
        llm_enabled=_as_bool(os.getenv("PM_AGENT_FILE_DETAIL_LLM_ENABLED", "false")),
    )
