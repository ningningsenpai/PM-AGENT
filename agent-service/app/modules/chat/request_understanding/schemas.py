"""多维请求理解的受限数据协议。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictSchema(BaseModel):
    """拒绝模型自行扩展动作、接口或存储字段。"""

    model_config = ConfigDict(extra="forbid")


RequestAction = Literal[
    "answer_project_question",
    "analyze_project_progress",
    "draft_next_stage_tasks",
    "analyze_project_risks",
    "check_project_constraints",
    "trace_information_source",
    "explain_project_history",
]
RequestSubject = Literal[
    "project",
    "project_progress",
    "next_stage_tasks",
    "risks",
    "project_constraints",
    "source_evidence",
    "project_history",
]


class RequestUnit(StrictSchema):
    """从复合输入拆出的一个最小只读或草案生成任务。"""

    id: str = Field(pattern=r"^unit-[1-9][0-9]*$")
    action: RequestAction
    subject: RequestSubject
    time_scope: Literal["current", "next_stage", "history", "unspecified"]
    depends_on: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0, le=1)
    source_text: str = Field(min_length=1, max_length=300)


class ContextUpdateSignal(StrictSchema):
    """值得跨轮保存的语义信号；是否生效仍由统一更新器决定。"""

    target: Literal[
        "project_constraint",
        "long_term_memory",
        "short_term_memory",
        "user_preference",
    ]
    operation: Literal["upsert", "deprecate", "resolve", "promote"] = "upsert"
    content: str = Field(min_length=1, max_length=2000)
    explicitness: Literal["explicit", "implicit", "uncertain"]
    scope: Literal["current_project", "current_project_user"]
    confidence: float = Field(ge=0, le=1)
    source_text: str = Field(min_length=1, max_length=500)
    requires_confirmation: bool


class PresentationPlan(StrictSchema):
    """只控制本轮回答，不能自行转化为持久偏好。"""

    detail_level: Literal["concise", "balanced", "detailed", "project_default"] = (
        "project_default"
    )
    format: Literal["adaptive", "table", "list", "markdown"] = "adaptive"
    language: Literal["zh-CN"] = "zh-CN"
    tone: Literal["project_default", "direct", "explanatory"] = "project_default"
    scope: Literal["current_turn"] = "current_turn"


class ModelRequestPlan(StrictSchema):
    """轻量请求理解模型唯一允许返回的内容。"""

    request_units: list[RequestUnit] = Field(default_factory=list, max_length=8)
    context_updates: list[ContextUpdateSignal] = Field(default_factory=list, max_length=8)
    presentation: PresentationPlan = Field(default_factory=PresentationPlan)
    requires_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_dependencies(self) -> ModelRequestPlan:
        ids = [unit.id for unit in self.request_units]
        if len(ids) != len(set(ids)):
            raise ValueError("请求单元 ID 不能重复")
        known = set(ids)
        graph: dict[str, list[str]] = {}
        for unit in self.request_units:
            if len(unit.depends_on) != len(set(unit.depends_on)):
                raise ValueError("请求单元依赖不能重复")
            if unit.id in unit.depends_on:
                raise ValueError("请求单元不能依赖自身")
            if not set(unit.depends_on) <= known:
                raise ValueError("请求单元引用了未知依赖")
            graph[unit.id] = unit.depends_on
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(unit_id: str) -> None:
            if unit_id in visiting:
                raise ValueError("请求单元依赖形成循环")
            if unit_id in visited:
                return
            visiting.add(unit_id)
            for dependency in graph.get(unit_id, []):
                visit(dependency)
            visiting.remove(unit_id)
            visited.add(unit_id)

        for unit_id in ids:
            visit(unit_id)
        if self.requires_clarification and not (self.clarification_question or "").strip():
            raise ValueError("需要澄清时必须提供问题")
        if not self.requires_clarification and self.clarification_question:
            raise ValueError("无需澄清时不能附带澄清问题")
        return self


class RequestDimension(StrictSchema):
    """兼容旧调用方的维度摘要，不作为执行依据。"""

    name: Literal[
        "progress",
        "planning",
        "risk",
        "constraint_check",
        "source_trace",
        "context_update",
        "presentation",
    ]
    confidence: float = Field(ge=0, le=1)
    evidence_text: str = Field(max_length=200)


class RequestPlan(ModelRequestPlan):
    """后端校验并补齐运行元数据后的最终请求计划。"""

    schema_version: Literal["2.0"] = "2.0"
    plan_id: str = Field(min_length=1, max_length=80)
    presentation: dict[str, str]
    planner: Literal["model", "deterministic_fallback"]
    prompt_version: str = Field(min_length=1, max_length=32)
    degraded: bool = False
    warnings: list[str] = Field(default_factory=list, max_length=8)
    dimensions: list[RequestDimension] = Field(default_factory=list, max_length=16)
    retrieval_focuses: list[str] = Field(default_factory=list, max_length=16)
    requested_actions: list[str] = Field(default_factory=list, max_length=16)

    @property
    def needs_clarification(self) -> bool:
        """兼容早期内部字段名。"""

        return self.requires_clarification
