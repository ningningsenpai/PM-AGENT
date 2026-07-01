import json
import re
import unittest
from pathlib import Path
from typing import Any

from app.project.context.model import ProjectContextModelClient, ProjectContextModelService


USER_HABIT_CATEGORIES = ("work", "life", "thinking", "specification", "tooling")


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
            habits_dir: str | Path,
            user_content: str | None = None,
            file_content: str | None = None):
        """测试 Qwen 模型输出并按分类写入用户习惯文件。"""
        # health = ProjectContextModelService.health()
        # self.assertTrue(health["healthy"])
        model = ProjectContextModelService()
        habits_path = Path(habits_dir)
        existing_habits = self._load_existing_habits(habits_path)
        result = model.generate_user_habits(
            existing_habits=existing_habits,
            user_content=user_content,
            project_content=file_content,
        )
        self._merge_user_habits_result(habits_path, result)
        return result

    def test_turn_user_habits(self):
        """多轮次测试 Qwen 模型输出。"""
        user_habits_path = Path(__file__).parent / "turn_user_habits" / "user_habits_test.md"
        habits_dir = Path(__file__).parent / "user_habits"
        self._reset_user_habits_dir(habits_dir)
        user_contents = [
            line.strip()
            for line in user_habits_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for user_content in user_contents:
            self.test_Qwen_model_user_habits(
                habits_dir=habits_dir,
                user_content=user_content,
                file_content="",
            )

    def _reset_user_habits_dir(self, habits_dir: Path) -> None:
        habits_dir.mkdir(parents=True, exist_ok=True)
        for category in USER_HABIT_CATEGORIES:
            self._write_category_file(habits_dir / f"{category}.json", category, [])

    def _load_existing_habits(self, habits_dir: Path) -> str:
        user_habits: list[dict[str, Any]] = []
        for category in USER_HABIT_CATEGORIES:
            payload = self._read_category_file(habits_dir / f"{category}.json", category)
            user_habits.extend(payload.get("user_habits", []))
        return json.dumps({"user_habits": user_habits}, ensure_ascii=False, indent=2)

    def _merge_user_habits_result(self, habits_dir: Path, result: str) -> None:
        payload = self._parse_model_json(result, habits_dir)
        grouped: dict[str, list[dict[str, Any]]] = {category: [] for category in USER_HABIT_CATEGORIES}
        for habit in payload.get("user_habits", []):
            category = habit.get("category")
            if category not in grouped:
                raise AssertionError(f"用户习惯分类非法：{category}")
            grouped[category].append(habit)

        habits_dir.mkdir(parents=True, exist_ok=True)
        for category, new_habits in grouped.items():
            path = habits_dir / f"{category}.json"
            current_payload = self._read_category_file(path, category)
            merged = {habit.get("id"): habit for habit in current_payload.get("user_habits", []) if habit.get("id")}
            for habit in new_habits:
                merged[habit["id"]] = habit
            self._write_category_file(path, category, list(merged.values()))

    def _parse_model_json(self, result: str, habits_dir: Path | None = None) -> dict[str, Any]:
        content = result.strip()
        match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", content, flags=re.DOTALL)
        if match:
            content = match.group(1).strip()
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise AssertionError("模型输出必须包含 JSON 对象")
        json_content = content[start : end + 1]
        if habits_dir is not None:
            debug_path = habits_dir / "last_raw_model_output.txt"
            debug_path.write_text(result, encoding="utf-8")
        try:
            data = json.loads(json_content)
        except json.JSONDecodeError as exc:
            if habits_dir is not None:
                debug_path = habits_dir / "last_invalid_model_json.txt"
                debug_path.write_text(json_content, encoding="utf-8")
            raise AssertionError(f"模型输出不是合法 JSON：第 {exc.lineno} 行第 {exc.colno} 列，{exc.msg}") from exc
        if not isinstance(data, dict):
            raise AssertionError("模型输出必须是 JSON 对象")
        if "user_habits" not in data or not isinstance(data["user_habits"], list):
            raise AssertionError("模型输出必须包含 user_habits 数组")
        return data

    def _read_category_file(self, path: Path, category: str) -> dict[str, Any]:
        if not path.exists():
            return {"category": category, "user_habits": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
        habits = payload.get("user_habits", [])
        if not isinstance(habits, list):
            raise AssertionError(f"{path.name} 中 user_habits 必须是数组")
        return {"category": category, "user_habits": habits}

    def _write_category_file(self, path: Path, category: str, user_habits: list[dict[str, Any]]) -> None:
        payload = {
            "category": category,
            "user_habits": user_habits,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == '__main__':
    unittest.main()
