"""报告生成请求、模型结论与引用约束。"""

from typing import Literal

from pydantic import Field

from app.core.schemas import Schema


class GenerateReport(Schema):
    kind: Literal["development", "risk"]


class ReportClaim(Schema):
    text: str = Field(min_length=1, max_length=3000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    category: Literal["fact", "risk", "suggestion", "uncertainty"]


class ReportDraft(Schema):
    title: str = Field(min_length=1, max_length=128)
    claims: list[ReportClaim] = Field(min_length=1, max_length=60)
