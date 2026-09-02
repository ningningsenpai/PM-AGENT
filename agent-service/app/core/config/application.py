"""业务后端基础设施配置。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.config.load_env_file import LoadConfig


def _load_env() -> None:
    LoadConfig()


@dataclass(frozen=True, slots=True)
class DatabaseConfig:
    url: str
    echo: bool
    pool_size: int
    max_overflow: int

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        _load_env()
        return cls(
            url=os.getenv(
                "PM_AGENT_DATABASE_URL",
                "mysql+asyncmy://pm_agent:pm_agent_dev@127.0.0.1:3306/pm_agent"
                "?charset=utf8mb4",
            ),
            echo=os.getenv("PM_AGENT_DATABASE_ECHO", "false").lower() == "true",
            pool_size=int(os.getenv("PM_AGENT_DATABASE_POOL_SIZE", "5")),
            max_overflow=int(os.getenv("PM_AGENT_DATABASE_MAX_OVERFLOW", "10")),
        )


@dataclass(frozen=True, slots=True)
class RedisConfig:
    url: str
    key_prefix: str

    @classmethod
    def from_env(cls) -> "RedisConfig":
        _load_env()
        return cls(
            url=os.getenv(
                "PM_AGENT_REDIS_URL",
                "redis://:pm-agent-dev@127.0.0.1:6379/1",
            ),
            key_prefix=os.getenv("PM_AGENT_REDIS_KEY_PREFIX", "pm-agent"),
        )


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    jwt_secret: str
    jwt_algorithm: str
    token_ttl_seconds: int

    @classmethod
    def from_env(cls) -> "SecurityConfig":
        _load_env()
        return cls(
            jwt_secret=os.getenv(
                "PM_AGENT_JWT_SECRET",
                "pm-agent-dev-secret-change-me",
            ),
            jwt_algorithm=os.getenv("PM_AGENT_JWT_ALGORITHM", "HS256"),
            token_ttl_seconds=int(os.getenv("PM_AGENT_TOKEN_TTL_SECONDS", "2592000")),
        )


@dataclass(frozen=True, slots=True)
class SnowflakeConfig:
    node_id: int

    @classmethod
    def from_env(cls) -> SnowflakeConfig:
        _load_env()
        raw_node_id = os.getenv("PM_AGENT_SNOWFLAKE_NODE_ID", "0")
        try:
            node_id = int(raw_node_id)
        except ValueError as exception:
            raise ValueError("雪花算法节点编号必须是 0 到 1023 的整数") from exception
        if not 0 <= node_id <= 1023:
            raise ValueError("雪花算法节点编号必须在 0 到 1023 之间")
        return cls(node_id=node_id)


@dataclass(frozen=True, slots=True)
class StorageConfig:
    endpoint: str
    access_key: str
    secret_key: str
    secure: bool
    bucket: str
    read_url_expiry_seconds: int

    @classmethod
    def from_env(cls) -> "StorageConfig":
        _load_env()
        endpoint = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
        return cls(
            endpoint=endpoint.replace("http://", "").replace("https://", ""),
            access_key=os.getenv("MINIO_ROOT_USER", "pm-agent"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "123456-pm-agent"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            bucket=os.getenv("MINIO_BUCKET", "pm-agent"),
            read_url_expiry_seconds=int(
                os.getenv("MINIO_READ_URL_EXPIRY_SECONDS", "300")
            ),
        )


@dataclass(frozen=True, slots=True)
class FileConfig:
    max_size_bytes: int
    ignored_directories: frozenset[str]
    ignored_file_names: frozenset[str]
    blocked_extensions: frozenset[str]
    blocked_mime_types: frozenset[str]

    @classmethod
    def from_env(cls) -> "FileConfig":
        _load_env()
        return cls(
            max_size_bytes=int(
                os.getenv("PM_AGENT_MAX_UPLOAD_FILE_SIZE_BYTES", "52428800")
            ),
            ignored_directories=frozenset(
                {".git", ".idea", ".vscode", "node_modules", ".venv", "__pycache__"}
            ),
            ignored_file_names=frozenset({".env", ".DS_Store"}),
            blocked_extensions=frozenset(
                {"exe", "dll", "so", "class", "jar", "war", "zip", "rar", "7z"}
            ),
            blocked_mime_types=frozenset(
                {"application/x-msdownload", "application/x-executable"}
            ),
        )
