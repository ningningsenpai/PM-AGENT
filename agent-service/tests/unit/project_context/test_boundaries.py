"""项目上下文模块依赖边界测试。"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

import app
import app.llm.orchestration as orchestration_package
import app.llm.prompts as prompts_package
import app.project_context as project_context_package
import app.project_context.index as index_package

_OLD_INDEX_MODULE = "app.modules.project.index_service"
_OLD_PROJECT_PACKAGE = "app.project"


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
        or module_name == "app.project_context.specification.service"
        or "ProjectSpecificationService" in names
        or "Session" in names
        or any(name.endswith("Repository") for name in names)
    )


def test_index_context_has_no_reverse_business_or_framework_dependency() -> None:
    package_root = Path(index_package.__file__).parent
    violations: dict[str, list[str]] = {}
    for source_file in package_root.glob("*.py"):
        imported = _import_details(source_file, "app.project_context.index")
        forbidden = sorted(
            module_name
            for module_name, names in imported
            if _is_forbidden_index_import(module_name, names)
        )
        if forbidden:
            violations[source_file.name] = forbidden

    assert not violations


def test_project_context_has_no_reverse_business_or_framework_dependency() -> None:
    package_root = Path(project_context_package.__file__).parent
    violations: dict[str, list[str]] = {}
    for source_file in package_root.rglob("*.py"):
        relative_path = source_file.relative_to(package_root).with_suffix("")
        current_package = ".".join(
            ("app", "project_context", *relative_path.parts[:-1])
        )
        imported = _import_details(source_file, current_package)
        forbidden = sorted(
            module_name
            for module_name, names in imported
            if any(
                module_name == prefix or module_name.startswith(f"{prefix}.")
                for prefix in ("app.modules", "fastapi", "sqlalchemy")
            )
            or module_name.endswith(".repository")
            or "Session" in names
            or any(name.endswith("Repository") for name in names)
        )
        if forbidden:
            violations[str(source_file.relative_to(package_root))] = forbidden

    assert not violations


def test_llm_prompts_have_no_business_or_infrastructure_dependency() -> None:
    package_root = Path(prompts_package.__file__).parent
    violations: dict[str, list[str]] = {}
    for source_file in package_root.rglob("*.py"):
        relative_path = source_file.relative_to(package_root).with_suffix("")
        current_package = ".".join(("app", "llm", "prompts", *relative_path.parts[:-1]))
        imported = _import_details(source_file, current_package)
        forbidden = sorted(
            module_name
            for module_name, names in imported
            if any(
                module_name == prefix or module_name.startswith(f"{prefix}.")
                for prefix in (
                    "app.modules",
                    "app.infrastructure",
                    "fastapi",
                    "minio",
                    "sqlalchemy",
                )
            )
            or module_name.endswith(".repository")
            or "Session" in names
            or any(
                name.endswith("Repository")
                or name.endswith("Service")
                or name in {"ObjectStorage", "StorageLocationFactory"}
                for name in names
            )
        )
        if forbidden:
            violations[str(source_file.relative_to(package_root))] = forbidden

    assert not violations


def test_application_has_no_legacy_project_import_or_module() -> None:
    app_root = Path(app.__file__).parent
    violations: list[str] = []
    for source_file in app_root.rglob("*.py"):
        relative_path = source_file.relative_to(app_root).with_suffix("")
        current_package = ".".join(("app", *relative_path.parts[:-1]))
        import_details = _import_details(source_file, current_package)
        if any(
            module_name == _OLD_INDEX_MODULE
            or module_name == _OLD_PROJECT_PACKAGE
            or module_name.startswith(f"{_OLD_PROJECT_PACKAGE}.")
            or (module_name == "app.modules.project" and "index_service" in names)
            for module_name, names in import_details
        ):
            violations.append(str(source_file.relative_to(app_root)))

    assert not violations
    assert not (app_root / "modules" / "project" / "index_service.py").exists()
    assert not (app_root / "project").exists()


def test_legacy_project_context_model_assets_are_removed() -> None:
    app_root = Path(app.__file__).parent
    legacy_symbols = (
        "ProjectContextModelAgent",
        "ProjectContextModelClient",
        "ProjectContextPrompt",
        "build_smoke_test_prompt",
        "load_model_config",
    )
    violations = {
        str(source_file.relative_to(app_root)): [
            symbol
            for symbol in legacy_symbols
            if symbol in source_file.read_text(encoding="utf-8")
        ]
        for source_file in app_root.rglob("*.py")
    }

    assert not {name: symbols for name, symbols in violations.items() if symbols}
    assert not hasattr(orchestration_package, "ProjectContextModelAgent")
