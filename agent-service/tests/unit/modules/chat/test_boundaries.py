"""Chat 模块依赖边界测试。"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

import app.modules.chat as chat_package


def _imported_modules(source_file: Path, current_package: str) -> set[str]:
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if node.level:
                module_name = resolve_name(
                    f"{'.' * node.level}{module_name}",
                    current_package,
                )
            if module_name:
                imported_modules.add(module_name)
    return imported_modules


def test_chat_module_does_not_depend_on_memory_retrieval_package() -> None:
    """验证 Chat 初始化模块不会反向依赖预留的信息召回包。"""
    package_root = Path(chat_package.__file__).parent
    violations: dict[str, list[str]] = {}
    for source_file in package_root.rglob("*.py"):
        relative_path = source_file.relative_to(package_root).with_suffix("")
        current_package = ".".join(
            ("app", "modules", "chat", *relative_path.parts[:-1])
        )
        forbidden = sorted(
            module
            for module in _imported_modules(source_file, current_package)
            if module == "app.memory" or module.startswith("app.memory.")
        )
        if forbidden:
            violations[str(source_file.relative_to(package_root))] = forbidden

    assert not violations


def test_chat_services_and_repositories_keep_dependency_direction() -> None:
    """服务不得反向依赖路由，外部业务模块不得直接构造 Chat 仓储。"""
    package_root = Path(chat_package.__file__).parent
    app_root = package_root.parent.parent
    violations = {}
    for source_file in app_root.rglob("*.py"):
        relative = source_file.relative_to(app_root).with_suffix("")
        current_package = ".".join(("app", *relative.parts[:-1]))
        imports = _imported_modules(source_file, current_package)
        if package_root in source_file.parents:
            if source_file.name in {
                "service.py",
                "repository.py",
                "rules.py",
                "snapshot.py",
            }:
                forbidden = sorted(
                    module for module in imports if module.endswith(".api")
                )
            else:
                forbidden = []
            if source_file.name == "repository.py":
                forbidden += sorted(
                    module for module in imports if module.endswith(".repository")
                )
        else:
            forbidden = sorted(
                module
                for module in imports
                if module.startswith("app.modules.chat.")
                and module.endswith(".repository")
            )
        if forbidden:
            violations[str(source_file.relative_to(app_root))] = forbidden
    assert not violations
