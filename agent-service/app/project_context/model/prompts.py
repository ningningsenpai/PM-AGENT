"""项目上下文模型 Prompt 模板。"""
from __future__ import annotations

from enum import Enum

from app.project.habits.prompts import ProjectHabitsPrompt

__all__ = ["ProjectContextPrompt", "build_smoke_test_prompt"]


class ProjectContextPrompt(str, Enum):
    """项目上下文模型 Prompt 模板。"""

    USER_HABITS = ProjectHabitsPrompt.USER_HABITS.value


def build_smoke_test_prompt() -> str:
    """构造项目上下文模型连通性测试 Prompt。"""
    return "请用一句中文回答：项目上下文模型连接正常。"
