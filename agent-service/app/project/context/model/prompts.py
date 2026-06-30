"""项目上下文模型 Prompt 模板。"""
from __future__ import annotations

from enum import Enum

from app.project.inner_prompts.long_term_memory import LongTermMemoryPrompt
from app.project.inner_prompts.project_file_detail import ProjectFileDetailPrompt
from app.project.inner_prompts.project_reading_content import ProjectReadingContentPrompt
from app.project.inner_prompts.project_specification import ProjectSpecificationPrompt
from app.project.inner_prompts.short_term_memory import ShortTermMemoryPrompt
from app.project.inner_prompts.user_habits import UserHabitsPrompt

__all__ = ["ProjectContextPrompt", "build_smoke_test_prompt"]


class ProjectContextPrompt(str, Enum):
    """项目上下文模型 Prompt 模板。"""

    USER_HABITS = UserHabitsPrompt.USER_HABITS.value
    PROJECT_SPECIFICATION = ProjectSpecificationPrompt.PROJECT_SPECIFICATION.value
    LONG_TERM_MEMORY = LongTermMemoryPrompt.LONG_TERM_MEMORY.value
    SHORT_TERM_MEMORY = ShortTermMemoryPrompt.SHORT_TERM_MEMORY.value
    PROJECT_FILE_DETAIL = ProjectFileDetailPrompt.PROJECT_FILE_DETAIL.value
    PROJECT_READING_CONTENT = ProjectReadingContentPrompt.PROJECT_READING_CONTENT.value


def build_smoke_test_prompt() -> str:
    """构造项目上下文模型连通性测试 Prompt。"""
    return "请用一句中文回答：项目上下文模型连接正常。"
