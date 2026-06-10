from pydantic import BaseModel


class AgentContext(BaseModel):
    """Java 调用 Python 时透传的上下文。"""

    trace_id: str
    user_id: str = "0"
    tenant_id: str = "0"
