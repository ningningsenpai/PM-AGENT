from pydantic import json

from app.project.context.model import ProjectContextModelClient
from app.project.inner_prompts import UserHabitsPrompt


class ProjectContextModelProcessor:
    """项目上下文模型处理服务。"""

    def __init__(self) -> None:
        self.client = ProjectContextModelClient()

    def user_habits(self, existing_habits: str | None = None, prompt: str | None = None) -> str:
        """ 生成用户习惯。"""
        if prompt is None:
            raise ValueError("提示不能为空")
        prompt = (
            f"{UserHabitsPrompt.USER_HABITS.value}\n\n"
            f"existing_habits_json：{existing_habits}\n\n"
            f"new_content：{prompt}"
        )
        print(prompt)
        return self.client.generate(prompt).content


