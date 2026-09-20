"""把受保护原型和增量覆盖层物化为可哈希的版本快照。"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent
SERVICE_ROOT = ROOT.parents[2]
REPOSITORY_ROOT = SERVICE_ROOT.parent
FIXTURE_ROOT = ROOT / "fixtures" / "student_management"
BASE_ROOT = SERVICE_ROOT / "project_test"


@dataclass(frozen=True, slots=True)
class MaterializedFixture:
    version: str
    root: Path
    manifest: dict


def _load_spec(version: str) -> dict:
    path = FIXTURE_ROOT / version / "version.json"
    if not path.is_file():
        raise ValueError(f"未知夹具版本：{version}")
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_relative(value: str) -> Path:
    pure = PurePosixPath(value)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts:
        raise ValueError(f"夹具路径不安全：{value}")
    return Path(*pure.parts)


def _excluded(relative: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def _copy_base(destination: Path, exclusions: list[str]) -> None:
    for source in sorted(BASE_ROOT.rglob("*")):
        if not source.is_file():
            continue
        relative = source.relative_to(BASE_ROOT).as_posix()
        if _excluded(relative, exclusions):
            continue
        target = destination / Path(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _apply_overlay(version: str, destination: Path) -> None:
    spec = _load_spec(version)
    parent = spec.get("inherits")
    if parent:
        _apply_overlay(parent, destination)
    overlay = FIXTURE_ROOT / version / "overlay"
    if overlay.is_dir():
        for source in sorted(overlay.rglob("*")):
            if not source.is_file():
                continue
            target = destination / source.relative_to(overlay)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for relative in spec.get("deletes", []):
        target = destination / _safe_relative(relative)
        if target.is_file():
            target.unlink()


def _manifest(version: str, destination: Path) -> dict:
    files = []
    for path in sorted(destination.rglob("*")):
        if not path.is_file():
            continue
        content = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(destination).as_posix(),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    digest_input = json.dumps(files, ensure_ascii=False, sort_keys=True).encode()
    return {
        "schemaVersion": "1.0",
        "fixture": "student_management",
        "version": version,
        "source": BASE_ROOT.relative_to(REPOSITORY_ROOT).as_posix(),
        "files": files,
        "fileCount": len(files),
        "snapshotSha256": hashlib.sha256(digest_input).hexdigest(),
    }


def materialize(version: str, destination: Path) -> MaterializedFixture:
    """在目标目录生成完整版本；调用方负责选择空目录。"""
    spec = _load_spec(version)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"物化目标目录必须为空：{destination}")
    destination.mkdir(parents=True, exist_ok=True)
    _copy_base(destination, list(spec.get("exclude", [])))
    _apply_overlay(version, destination)
    manifest = _manifest(version, destination)
    return MaterializedFixture(version=version, root=destination, manifest=manifest)


def text_files(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            result[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return result

