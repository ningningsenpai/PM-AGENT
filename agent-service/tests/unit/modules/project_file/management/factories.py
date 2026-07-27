"""项目文件管理测试对象工厂。"""

from app.core.config import FileConfig


def file_config() -> FileConfig:
    """构造文件管理规则配置。"""
    return FileConfig(
        max_size_bytes=1024,
        ignored_directories=frozenset({".git", "node_modules"}),
        ignored_file_names=frozenset({".env"}),
        blocked_extensions=frozenset({"exe"}),
        blocked_mime_types=frozenset({"application/x-msdownload"}),
    )
