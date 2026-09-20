"""校验冻结集、版本物化与证据锚点，并生成锁定清单。"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .dataset import dataset_sha256, load_dataset, resolve_annotation
from .fixture import ROOT, materialize, text_files

FREEZE_PATH = ROOT / "dataset" / "freeze.json"


def validate(workdir: Path, output: Path) -> dict:
    safe_output_root = (ROOT / "output").resolve()
    if not workdir.resolve().is_relative_to(safe_output_root):
        raise ValueError(f"物化工作目录必须位于 {safe_output_root} 内")
    questions, annotations = load_dataset()
    fixtures = {}
    resolved = []
    for version in ("v1", "v2", "v3"):
        destination = workdir / version
        if destination.exists():
            shutil.rmtree(destination)
        fixture = materialize(version, destination)
        fixtures[version] = fixture
    for question in questions:
        fixture = fixtures[question.version]
        resolved.append(
            resolve_annotation(annotations[question.id], text_files(fixture.root)).model_dump(mode="json")
        )
    result = {
        "schemaVersion": "1.0",
        "validatedAt": datetime.now(UTC).isoformat(),
        "datasetSha256": dataset_sha256(),
        "questionCount": len(questions),
        "splitCounts": dict(Counter(item.split for item in questions)),
        "categoryCounts": dict(Counter(item.category for item in questions)),
        "fixtureManifests": {version: item.manifest for version, item in fixtures.items()},
        "resolvedAnnotations": resolved,
    }
    frozen = json.loads(FREEZE_PATH.read_text(encoding="utf-8"))
    actual_snapshots = {
        version: {
            "fileCount": item.manifest["fileCount"],
            "snapshotSha256": item.manifest["snapshotSha256"],
        }
        for version, item in fixtures.items()
    }
    checks = {
        "datasetSha256": frozen.get("datasetSha256") == result["datasetSha256"],
        "questionCount": frozen.get("questionCount") == result["questionCount"],
        "splitCounts": frozen.get("splitCounts") == result["splitCounts"],
        "categoryCounts": frozen.get("categoryCounts") == result["categoryCounts"],
        "fixtureSnapshots": frozen.get("fixtureSnapshots") == actual_snapshots,
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise ValueError(f"冻结锁不匹配，必须先审阅数据变更：{failed}")
    result["freezeChecks"] = checks
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 50 题冻结集和全部证据锚点")
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.workdir.resolve(), args.output.resolve())
    print(f"冻结集校验通过：{result['questionCount']} 题，哈希 {result['datasetSha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
