"""项目文件解析 API。"""
from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, status

from app.project.context.detail_analysis.schemas import FileAnalysisRequest, FileAnalysisResult
from app.project.context.detail_analysis.file_content import FileContent

router = APIRouter(prefix="/api/v1/project-files", tags=["项目文件"])


@router.post("/analyze", response_model=FileAnalysisResult, response_model_by_alias=True)
async def analyze_project_file(
    request: FileAnalysisRequest,
    trace_id: str = Header(alias="X-Trace-Id", min_length=1, max_length=128),
) -> FileAnalysisResult:
    """接收 Java 提供的受控文件引用并同步返回文件详情解析结果。"""

