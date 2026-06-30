"""项目内置 Prompts 导出。"""
from __future__ import annotations

from app.project.inner_prompts.long_term_memory import LongTermMemoryPrompt
from app.project.inner_prompts.project_file_detail import ProjectFileDetailPrompt
from app.project.inner_prompts.project_reading_content import ProjectReadingContentPrompt
from app.project.inner_prompts.project_specification import ProjectSpecificationPrompt
from app.project.inner_prompts.short_term_memory import ShortTermMemoryPrompt
from app.project.inner_prompts.user_habits import UserHabitsPrompt

__all__ = [
    "UserHabitsPrompt",
    "ProjectSpecificationPrompt",
    "LongTermMemoryPrompt",
    "ShortTermMemoryPrompt",
    "ProjectFileDetailPrompt",
    "ProjectReadingContentPrompt",
]
