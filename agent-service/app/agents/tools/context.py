"""上下文条目、变更、报告及文件证据的只读工具。"""

from typing import Literal

from app.core.errors import AppException, ErrorCode
from app.core.identifiers import SnowflakeId
from pydantic import BaseModel, ConfigDict, Field

from .base import BaseAgentTool


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntriesInput(Input):
    kind: Literal["term", "habit", "short_memory", "long_memory", "project_rule"] | None = None
    query: str | None = Field(default=None, max_length=200)


class ChangesInput(Input):
    entry_id: SnowflakeId | None = None


class ReportInput(Input):
    kind: Literal["development", "risk"] | None = None
    report_id: SnowflakeId | None = None


class EvidenceInput(Input):
    file_id: int = Field(ge=1)
    start_line: int = Field(default=1, ge=1)
    end_line: int = Field(default=200, ge=1)


class EntriesOutput(BaseModel):
    entries: list[dict]


class ChangesOutput(BaseModel):
    changes: list[dict]


class ReportOutput(BaseModel):
    reports: list[dict]


class EvidenceOutput(BaseModel):
    fileId: int
    logicalPath: str
    contentHash: str
    startLine: int
    endLine: int
    totalLines: int
    text: str
    truncated: bool
    hasMore: bool
    redacted: bool


def current_project(context):
    if context.project_id is None:
        raise AppException(ErrorCode.PARAM_INVALID, "当前对话未关联项目")
    return context.project_id


class ListContextEntriesTool(BaseAgentTool):
    name = "list_context_entries"
    description = "读取当前用户和项目的有效词条、回答习惯、短期事项及长期决策，包含来源消息与版本。不会返回失效、过期、待确认或其他项目的事实。"
    input_model, output_model = EntriesInput, EntriesOutput

    def __init__(self, service):
        self.service = service

    async def execute(self, context, arguments):
        return EntriesOutput(
            entries=await self.service.list_entries(
                context.user_id,
                current_project(context),
                kind=arguments.kind,
                query=arguments.query,
            )
        )


class GetContextChangesTool(BaseAgentTool):
    name = "get_context_changes"
    description = "查询当前范围内学习条目的变更历史，核对纠正前后的内容、版本及对应用户原话；可按条目 ID 精确查询。历史内容不是当前有效事实。"
    input_model, output_model = ChangesInput, ChangesOutput

    def __init__(self, service):
        self.service = service

    async def execute(self, context, arguments):
        return ChangesOutput(
            changes=await self.service.changes(
                context.user_id, current_project(context), arguments.entry_id
            )
        )


class GetProjectReportTool(BaseAgentTool):
    name = "get_project_report"
    description = "读取当前项目已经生成的最新开发报告或风险报告，附生成时间和来源版本；不会生成新报告，旧报告不代表当前最新事实。"
    input_model, output_model = ReportInput, ReportOutput

    def __init__(self, service):
        self.service = service

    async def execute(self, context, arguments):
        reports = await self.service.list(
            context.user_id,
            current_project(context),
            arguments.kind,
            arguments.report_id,
        )
        return ReportOutput(
            reports=[
                {key: value for key, value in report.items() if key != "evidence"}
                for report in reports[:1]
            ]
        )


class ReadProjectFileEvidenceTool(BaseAgentTool):
    name = "read_project_file_evidence"
    description = "按当前项目文件 ID 与真实行范围读取脱敏原文，核实具体实现和引用。最多 200 行、32 KiB；返回实际行号、内容哈希、截断和是否有后续内容。不能读取任意路径或 URL。"
    input_model, output_model = EvidenceInput, EvidenceOutput
    timeout_seconds = 20

    def __init__(self, service):
        self.service = service

    async def execute(self, context, arguments):
        return EvidenceOutput.model_validate(
            await self.service.read_evidence(
                context.user_id,
                current_project(context),
                arguments.file_id,
                arguments.start_line,
                arguments.end_line,
            )
        )
