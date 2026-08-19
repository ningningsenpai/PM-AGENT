"""项目上下文模块依赖边界测试。"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

import app
import app.project.context.index as index_package

_OLD_INDEX_MODULE = "app.modules.project.index_service"


def _import_details(
    source_file: Path,
    current_package: str,
) -> list[tuple[str, set[str]]]:
    tree = ast.parse(source_file.read_text(encoding="utf-8"))
    imports: list[tuple[str, set[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(
                (alias.name, {alias.name.rsplit(".", 1)[-1]}) for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if node.level:
                module_name = resolve_name(
                    f"{'.' * node.level}{module_name}",
                    current_package,
                )
            imports.append((module_name, {alias.name for alias in node.names}))
    return imports


def _is_forbidden_index_import(module_name: str, names: set[str]) -> bool:
    forbidden_prefixes = ("app.modules", "fastapi", "sqlalchemy")
    return (
        any(
            module_name == prefix or module_name.startswith(f"{prefix}.")
            for prefix in forbidden_prefixes
        )
        or module_name.endswith(".repository")
        or module_name == "app.project.context.specification.service"
        or "ProjectSpecificationService" in names
        or "Session" in names
        or any(name.endswith("Repository") for name in names)
    )


def test_index_context_has_no_reverse_business_or_framework_dependency() -> None:
    package_root = Path(index_package.__file__).parent
    violations: dict[str, list[str]] = {}
    for source_file in package_root.glob("*.py"):
        imported = _import_details(source_file, "app.project.context.index")
        forbidden = sorted(
            module_name
            for module_name, names in imported
            if _is_forbidden_index_import(module_name, names)
        )
        if forbidden:
            violations[source_file.name] = forbidden

    assert not violations


def test_application_has_no_legacy_project_index_import_or_module() -> None:
    app_root = Path(app.__file__).parent
    violations: list[str] = []
    for source_file in app_root.rglob("*.py"):
        relative_path = source_file.relative_to(app_root).with_suffix("")
        current_package = ".".join(("app", *relative_path.parts[:-1]))
        import_details = _import_details(source_file, current_package)
        if any(
            module_name == _OLD_INDEX_MODULE
            or (module_name == "app.modules.project" and "index_service" in names)
            for module_name, names in import_details
        ):
            violations.append(str(source_file.relative_to(app_root)))

    assert not violations
    assert not (app_root / "modules" / "project" / "index_service.py").exists()
