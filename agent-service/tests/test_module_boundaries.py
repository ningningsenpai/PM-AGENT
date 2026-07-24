"""Python 模块化单体目录与依赖边界测试。"""
from __future__ import annotations

import ast
from pathlib import Path

MODULE_ROOT = Path(__file__).parents[1] / "app" / "modules"
REQUIRED_FILES = {
    "__init__.py",
    "api.py",
    "schemas.py",
    "models.py",
    "domain.py",
    "repository.py",
    "service.py",
    "errors.py",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_business_modules_should_have_vertical_layer_files() -> None:
    for module_name in ("auth", "user", "project", "project_file"):
        actual = {path.name for path in (MODULE_ROOT / module_name).glob("*.py")}
        assert REQUIRED_FILES <= actual


def test_services_should_not_depend_on_fastapi_request_layer() -> None:
    for service_path in MODULE_ROOT.glob("*/service.py"):
        assert all(
            not imported.startswith("fastapi")
            for imported in _imports(service_path)
        )


def test_repositories_should_not_depend_on_external_services() -> None:
    forbidden = (
        "app.infrastructure.redis",
        "app.infrastructure.storage",
        "app.llm",
    )
    for repository_path in MODULE_ROOT.glob("*/repository.py"):
        assert all(
            not imported.startswith(forbidden)
            for imported in _imports(repository_path)
        )
