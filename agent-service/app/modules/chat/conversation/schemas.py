"""会话与消息接口契约。"""

from typing import Annotated

from pydantic import Field, StringConstraints, field_serializer

from app.core.identifiers import SnowflakeId
from app.core.schemas import Schema
from app.core.time import ShanghaiDateTime

ConversationTitle = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)
]


class CreateConversation(Schema):
    project_id: SnowflakeId
    title: ConversationTitle | None = None


class RenameConversation(Schema):
    title: ConversationTitle


class SendMessage(Schema):
    content: str = Field(min_length=1, max_length=16000)


class ConversationView(Schema):
    id: SnowflakeId
    project_id: SnowflakeId
    title: str
    learned_message_id: int = Field(ge=0)
    active_run_id: SnowflakeId | None
    created_at: ShanghaiDateTime

    @field_serializer("learned_message_id")
    def serialize_cursor(self, value):
        return str(value)


class MessageView(Schema):
    id: SnowflakeId
    role: str
    content: str
    run_id: SnowflakeId
    created_at: ShanghaiDateTime
    request_key: str | None = None
