"""项目规范分批生成、截断恢复与发布完整性回归测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock

from app.core.errors import AppException
from app.infrastructure.storage import StorageLocationFactory
from app.llm.contracts import LLMAssistantTurn
from app.llm.structured import StructuredJsonGenerator
from app.project_context.file_detail.schemas import FileRuleCandidate
from app.project_context.specification.schemas import (
    ProjectSpecificationDocument,
    merge_specifications,
)
from app.project_context.specification.service import ProjectSpecificationService
from tests.unit.modules.project_file.analysis.factories import file_detail
from tests.unit.modules.project_file.factories import (
    project,
    project_file,
    storage_config,
)

_NOW = "2026-09-07T22:00:00"


def _document(rule_id: str) -> ProjectSpecificationDocument:
    return ProjectSpecificationDocument.model_validate(
        {
            "project_id": "10",
            "updated_at": _NOW,
            "project_specification": {
                "coding_rules": [
                    {
                        "id": rule_id,
                        "rule": f"规则 {rule_id}",
                        "scope": "backend",
                        "status": "active",
                        "confidence": "high",
                        "created_at": _NOW,
                        "updated_at": _NOW,
                    }
                ]
            },
            "changes": [
                {
                    "change_id": f"change-{rule_id}",
                    "change_type": "created",
                    "target_id": rule_id,
                    "summary": "新增规则",
                    "created_at": _NOW,
                }
            ],
            "ignored_items": [{"content": rule_id, "reason": "忽略临时状态"}],
        }
    )


def _turn(rule_id: str) -> LLMAssistantTurn:
    return LLMAssistantTurn(
        content=_document(rule_id).model_dump_json(exclude_unset=True),
        finish_reason="stop",
    )


def _service(candidate_count, turns, *, existing=None):
    file = project_file()
    file.file_type = "doc"
    file.detail_ref = "system/file_details/current.json"
    detail = file_detail(file).model_copy(
        update={
            "detail_ref": file.detail_ref,
            "rule_candidates": [
                FileRuleCandidate(
                    category="coding_rule",
                    text=f"候选规则 {index}",
                    confidence="high",
                    evidence=["明确的文档约定"],
                )
                for index in range(candidate_count)
            ],
        }
    )
    storage = Mock()
    storage.exists.side_effect = [existing is not None, True]
    storage.read_bytes.side_effect = (
        [existing.model_dump_json().encode()] if existing is not None else []
    ) + [detail.model_dump_json().encode()]
    client = SimpleNamespace(complete_turn=AsyncMock(side_effect=turns))
    service = ProjectSpecificationService(
        storage,
        StorageLocationFactory(storage_config()),
        StructuredJsonGenerator(client, max_tokens=16384, timeout_seconds=120),
    )
    return service, storage, client, file


def _batch_candidates(call):
    prompt = call.args[0][1]["content"]
    source_json = prompt.split("new_content（结构化规则候选）：\n", 1)[1].split(
        "\n\nsource_meta：", 1
    )[0]
    return [
        candidate["text"]
        for source in json.loads(source_json)
        for candidate in source["rule_candidates"]
    ]


class SpecificationBatchTest(IsolatedAsyncioTestCase):
    async def test_mixed_rule_field_names_are_corrected_before_strict_validation(self):
        payload = _document("coding-1").model_dump(mode="json")
        body = payload["project_specification"]
        coding = body["coding_rules"][0]
        coding["constraint"] = coding.pop("rule")
        body["risk_rules"] = [
            {**coding, "id": f"risk-{index}", "constraint": f"风险规则 {index}"}
            for index in range(4)
        ]
        service, storage, client, file = _service(
            1,
            [LLMAssistantTurn(content=json.dumps(payload), finish_reason="stop")],
            existing=_document("old"),
        )

        self.assertEqual("updated", await service.refresh(project(), [file]))

        client.complete_turn.assert_awaited_once()
        saved = ProjectSpecificationDocument.model_validate_json(
            storage.put_bytes.call_args.args[1]
        )
        self.assertEqual(["old", "coding-1"], [rule.id for rule in saved.project_specification.coding_rules])
        self.assertEqual(
            [f"风险规则 {index}" for index in range(4)],
            [rule.rule for rule in saved.project_specification.risk_rules],
        )
        self.assertNotIn('"constraint"', json.dumps(
            json.loads(storage.put_bytes.call_args.args[1])["project_specification"]["risk_rules"]
        ))

    async def test_conflicting_or_invalid_rule_fields_keep_old_specification(self):
        for changes in (
            {"constraint": "不同的正文"},
            {"rule": None, "constraint": "不能替代显式空值"},
            {"rule": "规则", "unknown_field": "不能忽略"},
            {"rule": ["错误类型"]},
            {"status": "invalid"},
        ):
            with self.subTest(changes=changes):
                payload = _document("invalid").model_dump(mode="json")
                payload["project_specification"]["coding_rules"][0].update(changes)
                service, storage, client, file = _service(
                    13,
                    [_turn("first"), LLMAssistantTurn(content=json.dumps(payload), finish_reason="stop")],
                    existing=_document("old"),
                )
                with self.assertRaises(AppException):
                    await service.refresh(project(), [file])
                self.assertEqual(2, client.complete_turn.await_count)
                storage.put_bytes.assert_not_called()

    async def test_large_single_source_is_split_without_losing_candidates(self):
        service, storage, client, file = _service(
            25, [_turn("one"), _turn("two"), _turn("three")],
            existing=_document("old"),
        )

        status = await service.refresh(project(), [file])

        self.assertEqual("updated", status)
        calls = client.complete_turn.await_args_list
        batches = [_batch_candidates(call) for call in calls]
        self.assertEqual([12, 12, 1], [len(batch) for batch in batches])
        self.assertEqual(
            [f"候选规则 {index}" for index in range(25)],
            [candidate for batch in batches for candidate in batch],
        )
        self.assertIn('"id": "one"', calls[1].args[0][1]["content"])
        storage.put_bytes.assert_called_once()
        saved = ProjectSpecificationDocument.model_validate_json(
            storage.put_bytes.call_args.args[1]
        )
        self.assertEqual(
            ["old", "one", "two", "three"],
            [rule.id for rule in saved.project_specification.coding_rules],
        )
        self.assertEqual(4, len(saved.changes))
        self.assertEqual(4, len(saved.ignored_items))

    async def test_truncated_batch_splits_and_only_complete_results_are_stored(self):
        service, storage, client, file = _service(
            4,
            [
                LLMAssistantTurn(content='{"截断":', finish_reason="length"),
                _turn("first-half"),
                _turn("second-half"),
            ],
        )

        self.assertEqual("updated", await service.refresh(project(), [file]))

        batches = [
            _batch_candidates(call) for call in client.complete_turn.await_args_list
        ]
        self.assertEqual([4, 2, 2], [len(batch) for batch in batches])
        self.assertEqual(batches[0], batches[1] + batches[2])
        storage.put_bytes.assert_called_once()
        saved = json.loads(storage.put_bytes.call_args.args[1])
        self.assertEqual(
            ["first-half", "second-half"],
            [rule["id"] for rule in saved["project_specification"]["coding_rules"]],
        )

    async def test_failure_in_later_batch_keeps_previous_stored_document(self):
        for failing_turn in (
            LLMAssistantTurn(content="{}", finish_reason="stop"),
            LLMAssistantTurn(content="", finish_reason="length"),
            LLMAssistantTurn(
                content=_document("wrong-project").model_copy(
                    update={"project_id": 99}
                ).model_dump_json(),
                finish_reason="stop",
            ),
        ):
            with self.subTest(turn=failing_turn):
                service, storage, client, file = _service(
                    13, [_turn("first"), failing_turn], existing=_document("old")
                )
                with self.assertRaises(AppException):
                    await service.refresh(project(), [file])
                self.assertEqual(2, client.complete_turn.await_count)
                storage.put_bytes.assert_not_called()

    def test_long_evidence_splits_before_candidate_count_limit(self):
        service, _, _, _ = _service(0, [])
        source = {
            "source_ref": {"file_id": 30},
            "rule_candidates": [
                {"text": "候选规则", "evidence": ["证据" * 1500]} for _ in range(6)
            ],
        }

        batches = service._batch_sources([source])

        self.assertGreater(len(batches), 1)
        candidates = [
            candidate
            for batch in batches
            for item in batch
            for candidate in item["rule_candidates"]
        ]
        self.assertEqual(source["rule_candidates"], candidates)

    def test_incremental_merge_preserves_stage_and_unmentioned_stage_fields(self):
        existing = _document("old")
        existing.project_specification.development_stage.current_stage = "开发中"
        existing.project_specification.development_stage.stage_goal = "完成文件解析"
        patch = ProjectSpecificationDocument.model_validate(
            {
                "project_id": "10",
                "updated_at": _NOW,
                "project_specification": {
                    "development_stage": {"next_focus": ["完善回归测试"]}
                },
            }
        )

        merged = merge_specifications(existing, patch)
        merged = merge_specifications(merged, _document("new"))

        stage = merged.project_specification.development_stage
        self.assertEqual("开发中", stage.current_stage)
        self.assertEqual("完成文件解析", stage.stage_goal)
        self.assertEqual(["完善回归测试"], stage.next_focus)
