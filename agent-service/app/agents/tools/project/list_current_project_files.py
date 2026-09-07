"""查询当前项目文件列表的只读 Agent 工具。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.agents.tools.base import BaseAgentTool
from app.agents.tools.schemas import ToolExecutionContext
from app.core.errors import AppException, ErrorCode
from app.modules.project_file.management.service import ProjectFileService
from pydantic import BaseModel, ConfigDict, Field


class ListCurrentProjectFilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    business_code: Literal["project", "user"] | None = Field(
        default=None,
        description="可选文件业务类型；留空时查询项目和用户公开文件。",
    )
    analysis_status: Literal["success", "pending", "failed", "unavailable"] | None = (
        None
    )


class CurrentProjectFileItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    business_code: str
    relative_path: str
    file_name: str
    extension: str | None
    content_type: str
    size_bytes: int
    status: str
    upload_status: str
    parse_attempts: int
    analysis_status: str = "pending"
    last_error_code: str | None = None
    last_error_message: str | None = None
    updated_at: datetime


class ListCurrentProjectFilesOutput(BaseModel):
    files: list[CurrentProjectFileItem] = Field(default_factory=list)
    total: int = Field(ge=0)


class ListCurrentProjectFilesTool(BaseAgentTool):
    """通过 ProjectFileService 查询当前对话项目的公开文件。"""

    name = "list_current_project_files"
    description = (
        "查询当前对话关联项目的公开文件列表和处理状态，不返回存储路径或下载地址。"
    )
    input_model = ListCurrentProjectFilesInput
    output_model = ListCurrentProjectFilesOutput

    def __init__(self, files: ProjectFileService) -> None:
        self._files = files

    async def execute(
        self,
        context: ToolExecutionContext,
        arguments: BaseModel,
    ) -> BaseModel:
        if context.project_id is None:
            raise AppException(ErrorCode.PARAM_INVALID, "当前对话未指定项目")
        parameters = ListCurrentProjectFilesInput.model_validate(arguments)
        files = await self._files.list_files(
            context.user_id,
            context.project_id,
            parameters.business_code,
        )
        items = [CurrentProjectFileItem.model_validate(file) for file in files]
        if parameters.analysis_status:
            items = [
                item
                for item in items
                if item.analysis_status == parameters.analysis_status
            ]
        return ListCurrentProjectFilesOutput(files=items, total=len(items))
