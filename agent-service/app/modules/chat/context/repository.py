"""MinIO 上下文服务的请求级事务句柄。"""

from .._persistence import ChatRepositoryBase


class ContextRepository(ChatRepositoryBase):
    """不保存上下文正文，只向现有服务暴露同一请求的数据库会话。"""
