"""项目文件双子包边界测试。"""

from __future__ import annotations

import ast
from importlib.util import resolve_name
from pathlib import Path

import pytest

import app.modules.project_file as project_file_package
from app.modules.project_file.analysis.service import ProjectFileAnalysisService
from app.modules.project_file.management.service import ProjectFileService


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


@pytest.mark.parametrize(
    ("package_name", "forbidden_package"),
    [
        ("management", "app.modules.project_file.analysis"),
        ("analysis", "app.modules.project_file.management"),
    ],
)
def test_subpackages_do_not_import_each_other(
    package_name: str,
    forbidden_package: str,
) -> None:
    """验证文件管理与文件分析子包之间不存在直接依赖。

    @Param package_name: 待扫描的项目文件业务子包名称。
    @Param forbidden_package: 当前子包禁止导入的另一侧完整包路径。
    @Return: None，目标子包内不存在跨边界导入。
    """
    package_root = Path(project_file_package.__file__).parent / package_name
    current_package = f"app.modules.project_file.{package_name}"
    violations = {
        source_file.name: sorted(
            module
            for module in _imported_modules(source_file, current_package)
            if module == forbidden_package
            or module.startswith(f"{forbidden_package}.")
        )
        for source_file in package_root.glob("*.py")
    }

    assert not {name: modules for name, modules in violations.items() if modules}


def test_root_package_exports_public_services() -> None:
    """验证根包继续公开导出两个业务 Service。

    @Param: 无显式入参。
    @Return: None，根包导出与两个子包中的 Service 类完全一致。
    """
    assert project_file_package.ProjectFileService is ProjectFileService
    assert (
        project_file_package.ProjectFileAnalysisService
        is ProjectFileAnalysisService
    )
