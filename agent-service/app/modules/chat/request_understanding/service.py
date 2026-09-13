"""将一条用户消息拆成可独立执行的多个业务维度。"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from typing import ClassVar
from uuid import uuid4

from app.llm.structured import StructuredJsonGenerator

from .schemas import (
    ContextUpdateSignal,
    ModelRequestPlan,
    PresentationPlan,
    RequestDimension,
    RequestPlan,
    RequestUnit,
)

logger = logging.getLogger(__name__)
REQUEST_PLAN_PROMPT_VERSION = "request-plan-v2"

_REQUEST_PLAN_RULES = """
你只负责把一条用户消息拆成受限的项目管理请求计划，不回答问题，也不调用工具。
要求：
1. 一个 request_unit 只表达一个动作，ID 按 unit-1、unit-2 顺序生成；
2. action、subject、time_scope 只能使用 JSON Schema 中的枚举；
3. depends_on 只引用当前结果中存在的请求单元，不得自环或成环；
4. source_text 必须逐字来自用户消息，不能改写；
5. “这次详细/用表格”只写 presentation，scope 固定 current_turn；
6. 只有“以后/今后/默认/请记住/本项目”，或“设为规则/偏好/目标”等明确持久化动作，才可产生 context_updates；
7. 明确的必须、禁止、目标变更或“以后/默认”偏好可标 explicit；只有 explicit 且 confidence >= 0.85 时 requires_confirmation=false；建议、疑问、假设标 implicit 或 uncertain，并要求确认；
8. 任务和风险只允许作为分析、建议或进度风险检查，不产生正式业务写入动作；
9. 不得输出项目 ID、用户 ID、文件路径、接口、类名、SQL、工具名或数据库字段；
10. 信息不足以安全确定上下文更新对象时 requires_clarification=true，并提出一个最小问题；
11. 普通项目问答至少生成 answer_project_question 单元。

只返回以下形状的 JSON，空集合使用 []：
{
  "request_units": [{
    "id": "unit-1",
    "action": "answer_project_question | analyze_project_progress | draft_next_stage_tasks | analyze_project_risks | check_project_constraints | trace_information_source | explain_project_history",
    "subject": "project | project_progress | next_stage_tasks | risks | project_constraints | source_evidence | project_history",
    "time_scope": "current | next_stage | history | unspecified",
    "depends_on": [],
    "confidence": 0.0,
    "source_text": "用户原文片段"
  }],
  "context_updates": [{
    "target": "project_constraint | long_term_memory | short_term_memory | user_preference",
    "operation": "upsert | deprecate | resolve | promote",
    "content": "准备保存的语义内容",
    "explicitness": "explicit | implicit | uncertain",
    "scope": "current_project | current_project_user",
    "confidence": 0.0,
    "source_text": "用户原文片段",
    "requires_confirmation": true
  }],
  "presentation": {
    "detail_level": "concise | balanced | detailed | project_default",
    "format": "adaptive | table | list | markdown",
    "language": "zh-CN",
    "tone": "project_default | direct | explanatory",
    "scope": "current_turn"
  },
  "requires_clarification": false,
  "clarification_question": null
}
""".strip()


class RequestUnderstandingService:
    """模型优先、确定性降级的单次多标签请求理解器。"""

    _RULES: ClassVar[dict[str, tuple[str, ...]]] = {
        "progress": ("进度", "完成情况", "做到哪", "当前状态"),
        "planning": ("下一阶段", "规划", "排期", "开发目标"),
        "risk": ("风险", "隐患", "阻塞", "延期"),
        "constraint_check": ("规则", "约束", "规范", "遵守", "违反"),
        "source_trace": ("出处", "来自哪里", "依据", "原文"),
        "presentation": ("详细", "简洁", "表格", "逐项", "格式"),
    }

    def __init__(
        self,
        generator: StructuredJsonGenerator | None = None,
        *,
        max_input_chars: int = 4000,
    ) -> None:
        self._generator = generator
        self._max_input_chars = max_input_chars

    async def analyze_with_model(self, message: str) -> RequestPlan:
        """只执行一次小型结构化调用；任何不可信结果均失败关闭到只读基线。"""

        normalized = message.strip()
        if not normalized or self._generator is None:
            return self.analyze(message)
        prompt = f"{_REQUEST_PLAN_RULES}\n\n用户消息：\n{normalized[: self._max_input_chars]}"
        try:
            output = await self._generator.generate(prompt, ModelRequestPlan)
            self._validate_source_quotes(normalized, output)
            output = self._enforce_confirmation_policy(output)
            return self._finalize(output, message, planner="model")
        except Exception as exception:  # noqa: BLE001 -- 模型失败不能阻断普通问答。
            logger.warning(
                "多维请求理解降级 promptVersion=%s errorType=%s",
                REQUEST_PLAN_PROMPT_VERSION,
                type(exception).__name__,
            )
            plan = self.analyze(message)
            plan.warnings.append("请求理解模型不可用，已使用确定性安全基线")
            return plan

    def analyze(self, message: str) -> RequestPlan:
        """不访问外部系统的确定性基线，供故障降级和单元测试使用。"""

        output = self._deterministic_output(message)
        return self._finalize(
            output,
            message,
            planner="deterministic_fallback",
            degraded=self._generator is not None,
        )

    def _deterministic_output(self, message: str) -> ModelRequestPlan:
        units: list[RequestUnit] = []

        def add_unit(action: str, subject: str, time_scope: str, phrase: str) -> None:
            if any(unit.action == action for unit in units):
                return
            units.append(
                RequestUnit(
                    id=f"unit-{len(units) + 1}",
                    action=action,
                    subject=subject,
                    time_scope=time_scope,
                    confidence=0.9,
                    source_text=phrase,
                )
            )

        matches = self._matched_terms(message)
        if "progress" in matches:
            add_unit(
                "analyze_project_progress",
                "project_progress",
                "current",
                matches["progress"],
            )
        if "planning" in matches or "制定任务" in message or "安排任务" in message:
            add_unit(
                "draft_next_stage_tasks",
                "next_stage_tasks",
                "next_stage",
                matches.get("planning") or "制定任务",
            )
        if "risk" in matches:
            add_unit("analyze_project_risks", "risks", "current", matches["risk"])
        if "constraint_check" in matches:
            add_unit(
                "check_project_constraints",
                "project_constraints",
                "current",
                matches["constraint_check"],
            )
        if "source_trace" in matches:
            add_unit(
                "trace_information_source",
                "source_evidence",
                "history",
                matches["source_trace"],
            )
        if not units:
            add_unit(
                "answer_project_question",
                "project",
                "unspecified",
                message[:300] or "项目问题",
            )

        progress_id = next(
            (unit.id for unit in units if unit.action == "analyze_project_progress"),
            None,
        )
        if progress_id:
            for unit in units:
                if unit.action == "draft_next_stage_tasks":
                    unit.depends_on = [progress_id]

        presentation = PresentationPlan(
            detail_level=(
                "detailed"
                if "详细" in message
                else "concise"
                if "简洁" in message
                else "project_default"
            ),
            format="table" if "表格" in message else "adaptive",
        )
        return ModelRequestPlan(
            request_units=units,
            context_updates=self._deterministic_context_signals(message),
            presentation=presentation,
        )

    def _deterministic_context_signals(self, message: str) -> list[ContextUpdateSignal]:
        if not self._is_context_update(message):
            return []
        persistent = self._source_fragment(message)
        if any(
            word in message
            for word in (
                "回答",
                "回复",
                "输出",
                "格式",
                "语气",
                "详细",
                "简洁",
                "表格",
            )
        ):
            target = "user_preference"
            scope = "current_project_user"
        elif any(word in message for word in ("目标", "里程碑", "发展方向")):
            target = "long_term_memory"
            scope = "current_project"
        else:
            target = "project_constraint"
            scope = "current_project"
        uncertain = any(
            word in message
            for word in ("也许", "可能", "或许", "建议", "考虑", "可不可以")
        )
        explicit_markers = (
            "必须",
            "禁止",
            "不得",
            "请记住",
            "设为",
            "设定",
            "设置",
            "添加为",
            "记录为",
            "改为",
        )
        if target == "user_preference":
            explicit_markers += ("以后", "今后", "默认")
        explicit = not uncertain and any(word in message for word in explicit_markers)
        return [
            ContextUpdateSignal(
                target=target,
                content=message.strip()[:2000],
                explicitness="explicit" if explicit else "implicit",
                scope=scope,
                confidence=0.94 if explicit else 0.72,
                source_text=persistent,
                requires_confirmation=not explicit,
            )
        ]

    def _finalize(
        self,
        output: ModelRequestPlan,
        message: str,
        *,
        planner: str,
        degraded: bool = False,
    ) -> RequestPlan:
        return RequestPlan(
            plan_id=f"req_{uuid4().hex}",
            planner=planner,
            prompt_version=REQUEST_PLAN_PROMPT_VERSION,
            degraded=degraded,
            request_units=output.request_units,
            context_updates=output.context_updates,
            presentation={
                "detail_level": output.presentation.detail_level,
                "format": output.presentation.format,
            },
            requires_clarification=output.requires_clarification,
            clarification_question=output.clarification_question,
            dimensions=self._dimensions(message, output),
            retrieval_focuses=self._retrieval_focuses(output) or ["auto"],
            requested_actions=self._requested_actions(output),
        )

    def _dimensions(
        self, message: str, output: ModelRequestPlan
    ) -> list[RequestDimension]:
        matches = self._matched_terms(message)
        dimensions = [
            RequestDimension(name=name, confidence=0.92, evidence_text=phrase)
            for name, phrase in matches.items()
        ]
        if output.context_updates and not any(
            item.name == "context_update" for item in dimensions
        ):
            dimensions.append(
                RequestDimension(
                    name="context_update",
                    confidence=max(item.confidence for item in output.context_updates),
                    evidence_text=output.context_updates[0].source_text[:200],
                )
            )
        return dimensions

    @staticmethod
    def _retrieval_focuses(output: ModelRequestPlan) -> list[str]:
        mapping = {
            "analyze_project_progress": ("memory", "files"),
            "draft_next_stage_tasks": ("memory", "files"),
            "analyze_project_risks": ("specification", "files"),
            "check_project_constraints": ("specification", "files"),
            "trace_information_source": ("files", "changes"),
            "explain_project_history": ("memory", "changes"),
            "answer_project_question": ("auto",),
        }
        return list(
            dict.fromkeys(
                focus
                for unit in output.request_units
                for focus in mapping.get(unit.action, ("auto",))
            )
        )

    @staticmethod
    def _requested_actions(output: ModelRequestPlan) -> list[str]:
        actions: list[str] = []
        if any(
            unit.action == "draft_next_stage_tasks" for unit in output.request_units
        ):
            actions.append("draft_next_stage_suggestions")
        if output.context_updates:
            actions.append("propose_context_update")
        return list(dict.fromkeys(actions))

    def _matched_terms(self, message: str) -> dict[str, str]:
        return {
            name: matched
            for name, words in self._RULES.items()
            if (matched := next((word for word in words if word in message), None))
            is not None
        }

    @staticmethod
    def _validate_source_quotes(message: str, output: ModelRequestPlan) -> None:
        quotes: Iterable[str] = [unit.source_text for unit in output.request_units] + [
            item.source_text for item in output.context_updates
        ]
        if any(quote not in message for quote in quotes):
            raise ValueError("请求计划引用了用户消息中不存在的原文")

    @staticmethod
    def _enforce_confirmation_policy(output: ModelRequestPlan) -> ModelRequestPlan:
        updates = []
        for item in output.context_updates:
            must_confirm = item.explicitness != "explicit" or item.confidence < 0.85
            updates.append(
                item.model_copy(
                    update={
                        # 是否直接生效属于后端策略，不能让模型把明确指令误降级为待确认。
                        "requires_confirmation": must_confirm
                    }
                )
            )
        return output.model_copy(update={"context_updates": updates})

    @staticmethod
    def _source_fragment(message: str) -> str:
        compact = re.sub(r"\s+", " ", message.strip())
        return compact[:500] or "项目指令"

    @staticmethod
    def _is_context_update(message: str) -> bool:
        persistent = any(
            word in message
            for word in (
                "以后",
                "今后",
                "默认",
                "本项目",
                "请记住",
                "设定规则",
                "设置规则",
                "设为规则",
                "添加为项目规则",
                "记录为规则",
                "设为偏好",
                "设置偏好",
                "设为目标",
                "设置目标",
            )
        )
        directive = any(
            word in message
            for word in (
                "必须",
                "禁止",
                "不得",
                "希望",
                "偏好",
                "目标",
                "里程碑",
                "详细",
                "简洁",
                "表格",
                "规则",
                "约束",
            )
        )
        return persistent and directive
