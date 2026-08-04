"""Agent 工具安全执行器。"""
from __future__ import annotations

import asyncio
import json
from time import perf_counter

from pydantic import ValidationError

from app.agents.tools.registry import ToolRegistry
from app.agents.tools.schemas import ToolExecutionContext, ToolExecutionResult
from app.core.errors import AppException, ErrorCode
from app.core.logger import get_logger
from app.llm.contracts import LLMToolCall

logger = get_logger(__name__)


class ToolExecutor:
    """统一完成工具查找、参数校验、门禁、超时和结果校验。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def execute(
        self,
        call: LLMToolCall,
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        started_at = perf_counter()
        tool = self._registry.get(call.name)
        if tool is None:
            return self._failed(
                call,
                {},
                ErrorCode.TOOL_NOT_REGISTERED,
                f"工具未注册：{call.name}",
                started_at,
            )

        try:
            raw_arguments = json.loads(call.arguments_json or "{}")
            if not isinstance(raw_arguments, dict):
                raise ValueError("工具参数必须是 JSON 对象")
            arguments = tool.input_model.model_validate(raw_arguments)
        except (json.JSONDecodeError, ValidationError, ValueError) as exception:
            return self._failed(
                call,
                {},
                ErrorCode.TOOL_ARGUMENT_INVALID,
                f"工具参数不合法：{exception}",
                started_at,
            )

        input_data = arguments.model_dump(mode="json")
        if tool.requires_confirmation:
            return ToolExecutionResult(
                call_id=call.id,
                tool_name=call.name,
                status="confirmation_required",
                input=input_data,
                error_code="TOOL_CONFIRMATION_REQUIRED",
                error_message="该工具需要用户确认后执行",
                duration_ms=self._duration_ms(started_at),
            )

        try:
            async with asyncio.timeout(tool.timeout_seconds):
                raw_output = await tool.execute(context, arguments)
            output = tool.output_model.model_validate(raw_output)
        except TimeoutError:
            return self._failed(
                call,
                input_data,
                ErrorCode.TOOL_EXECUTION_TIMEOUT,
                "工具执行超时",
                started_at,
            )
        except AppException as exception:
            return self._failed(
                call,
                input_data,
                exception.error,
                exception.message,
                started_at,
            )
        except (ValidationError, ValueError) as exception:
            return self._failed(
                call,
                input_data,
                ErrorCode.TOOL_EXECUTION_FAILED,
                f"工具返回格式不合法：{exception}",
                started_at,
            )
        except Exception:
            logger.exception(
                "工具执行异常 action=agent.tool.execute toolName=%s callId=%s",
                call.name,
                call.id,
            )
            return self._failed(
                call,
                input_data,
                ErrorCode.TOOL_EXECUTION_FAILED,
                "工具执行失败",
                started_at,
            )

        return ToolExecutionResult(
            call_id=call.id,
            tool_name=call.name,
            status="success",
            input=input_data,
            output=output.model_dump(mode="json"),
            duration_ms=self._duration_ms(started_at),
        )

    @staticmethod
    def _failed(
        call: LLMToolCall,
        input_data: dict,
        error: ErrorCode,
        message: str,
        started_at: float,
    ) -> ToolExecutionResult:
        return ToolExecutionResult(
            call_id=call.id,
            tool_name=call.name,
            status="failed",
            input=input_data,
            error_code=error.name,
            error_message=message,
            duration_ms=ToolExecutor._duration_ms(started_at),
        )

    @staticmethod
    def _duration_ms(started_at: float) -> int:
        return max(0, round((perf_counter() - started_at) * 1000))
