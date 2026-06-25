from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
import os

from app.core.config.load_env_file import LoadConfig

__all__ = ["get_storage_settings", "MinIOConfig"]

@dataclass
class MinIOConfig:
    """MinIO 对象存储配置。"""

    endpoint: str = "localhost:9000"
    access_key: str = "pm-agent"
    secret_key: str = "123456-pm-agent"
    bucket: str = "pm-agent"
    secure: bool = False
    public_endpoint: str = "http://localhost:9000"
    max_file_size_mb: int = 50

    @property
    def public_base_url(self) -> str:
        """返回去掉末尾斜杠的公开访问前缀。"""
        return self.public_endpoint.rstrip("/")

    @property
    def public_host(self) -> str:
        """返回公开访问地址的主机名和端口。"""
        parsed = urlparse(self.public_base_url)
        return parsed.netloc


class StorageSettings:
    """对象存储配置。"""

    def __init__(self) -> None:
        """初始化MinIO对象存储配置。"""
        self.minio = MinIOConfig(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.getenv("MINIO_ROOT_USER", "pm-agent"),
            secret_key=os.getenv("MINIO_ROOT_PASSWORD", "123456-pm-agent"),
            bucket=os.getenv("MINIO_BUCKET", "pm-agent"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            public_endpoint=os.getenv("MINIO_PUBLIC_ENDPOINT", "http://localhost:9000"),
            max_file_size_mb=int(os.getenv("MINIO_MAX_FILE_SIZE_MB", 50)),
        )

@lru_cache()
def get_storage_settings() -> StorageSettings:
    LoadConfig()
    return StorageSettings()