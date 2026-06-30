import unittest
from pathlib import Path

from app.project.context.model import ProjectContextModelClient, ProjectContextModelService


class MyTestCase(unittest.TestCase):
    def test_Qwen_health(self):
        """测试 Qwen 连通性。"""
        health = ProjectContextModelService.health()
        self.assertTrue(health["healthy"])

    def test_Qwen_model(self):
        """测试 Qwen 模型读取文件输出。"""
        health = ProjectContextModelService.health()
        self.assertTrue(health["healthy"])
        model = ProjectContextModelClient()
        path = Path(__file__).parent / "User_Habits.json"
        existing_habits = path.read_text(encoding="utf-8")
        result = model.generate(
            f"{existing_habits}\n\n"
            f"明天上午帮我点一杯饮品，你会选择什么？"
        )
        print(result)

    def test_Qwen_model_user_habits(
            self,
            input_path: str | Path | None, output_path: str | Path,
            user_content: str | None = None, file_content: str | None = None):
        """测试 Qwen 模型输出。"""
        health = ProjectContextModelService.health()
        self.assertTrue(health["healthy"])
        model = ProjectContextModelService()
        existing_habits = ""
        if input_path is not None:
            existing_habits = Path(input_path).read_text(encoding="utf-8")
        result = model.generate_user_habits(
            existing_habits=existing_habits,
            user_content=user_content,
            project_content=file_content,
        )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result, encoding="utf-8")


    def test_turn_user_habits(self):
        """多轮次测试 Qwen 模型输出。"""
        user_habits_path = Path(__file__).parent / "turn_user_habits" / "drink_habits.md"
        output_dir = Path(__file__).parent / "user_habits_results"
        user_contents = [
            line.strip()
            for line in user_habits_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        input_path: Path | None = None
        for row, user_content in enumerate(user_contents):
            if row != 0:
                input_path = output_dir / f"{row - 1}-user_habits.json"
            self.test_Qwen_model_user_habits(
                input_path=input_path,
                output_path=output_dir / f"{row}-user_habits.json",
                user_content=user_content,
                file_content="",
            )



if __name__ == '__main__':
    unittest.main()
