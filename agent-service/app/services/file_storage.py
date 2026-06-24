"""文件存储兼容导出。"""
from __future__ import annotations

from app.project.files.service import ProjectFileService as MinIOFileStorage

__all__ = ["MinIOFileStorage"]
