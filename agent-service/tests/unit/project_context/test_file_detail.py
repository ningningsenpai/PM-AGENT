"""文件语义分析服务测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from pydantic import ValidationError

from app.llm.contracts import LLMAssistantTurn
from app.llm.structured import (
    StructuredJsonGenerator,
    StructuredOutputError,
    StructuredOutputTruncatedError,
)
from app.llm.telemetry import capture_calls
from app.project_context.file_detail.extraction import ExtractedFileContent
from app.project_context.file_detail.schemas import (
    FileDetailSemanticOutput,
    FileRuleCandidate,
    FileSemanticAnalysisRequest,
)
from app.project_context.file_detail.service import FileSemanticAnalysisService


def _request() -> FileSemanticAnalysisRequest:
    return FileSemanticAnalysisRequest(
        user_id=1,
        project_id=10,
        business="project",
        file_id=30,
        filename="README.md",
        file_url="",
        file_type="md",
        storage_uuid="file-uuid",
        storage_name="README-file-uuid.md",
        detail_ref="system/file_details/README-file-uuid.json",
        original_path="README.md",
        minio_path="users/1/projects/10/project/README-file-uuid.md",
        size_bytes=4,
        content_type="text/markdown",
        content_hash="hash",
    )


def _extracted(text: str) -> ExtractedFileContent:
    return ExtractedFileContent(type="text", text=text)


def _semantic() -> FileDetailSemanticOutput:
    return FileDetailSemanticOutput(
        module="backend",
        kind="documentation",
        file_type="doc",
        language="markdown",
        importance="high",
        summary="项目约束说明",
        keywords=["FastAPI"],
        role="说明后端约束",
        content_slices=[],
        related_topics=[],
        related_files=[],
        risk_flags=[],
        sensitive_flags=[],
        evidence=[],
        parser={"strategy": "llm_enhanced"},
        rule_candidates=[
            FileRuleCandidate(
                category="technical_constraint",
                text="后端使用 FastAPI",
                confidence="high",
                evidence=["文档明确声明后端技术栈"],
            )
        ],
    )


class FileSemanticAnalysisServiceTest(IsolatedAsyncioTestCase):
    async def test_missing_required_field_gets_one_full_schema_correction(self):
        payload = _semantic().model_dump()
        payload.pop("keywords")
        client = SimpleNamespace(
            complete_turn=AsyncMock(
                side_effect=[
                    LLMAssistantTurn(content=json.dumps(payload), finish_reason="stop"),
                    LLMAssistantTurn(
                        content=_semantic().model_dump_json(), finish_reason="stop"
                    ),
                ]
            )
        )
        service = FileSemanticAnalysisService(
            StructuredJsonGenerator(client, max_tokens=24576, timeout_seconds=180),
            max_semantic_input_bytes=1024,
        )
        events = []
        with capture_calls(events):
            result = await service.analyze(_request(), _extracted("后端使用 FastAPI"))
        self.assertEqual("success", result.status)
        self.assertEqual(["FastAPI"], result.detail.keywords)
        self.assertEqual(2, client.complete_turn.await_count)
        correction = client.complete_turn.await_args.args[0][1]["content"]
        self.assertIn("requiredSchema", correction)
        self.assertIn("keywords", correction)
        self.assertEqual("missing", events[0]["errors"][0]["type"])
        self.assertEqual("validation", events[0]["type"])

    async def test_repeated_missing_field_stays_failed_without_partial_detail(self):
        payload = _semantic().model_dump()
        payload.pop("keywords")
        client = SimpleNamespace(
            complete_turn=AsyncMock(
                return_value=LLMAssistantTurn(
                    content=json.dumps(payload), finish_reason="stop"
                )
            )
        )
        service = FileSemanticAnalysisService(
            StructuredJsonGenerator(client, max_tokens=24576, timeout_seconds=180),
            max_semantic_input_bytes=1024,
        )
        result = await service.analyze(_request(), _extracted("后端使用 FastAPI"))
        self.assertEqual("failed", result.status)
        self.assertIsNone(result.detail)
        self.assertEqual(2, client.complete_turn.await_count)

    async def test_truncated_output_is_not_retried_as_field_correction(self):
        generator = SimpleNamespace(
            generate=AsyncMock(side_effect=StructuredOutputTruncatedError("输出不完整"))
        )
        result = await FileSemanticAnalysisService(
            generator,
            max_semantic_input_bytes=1024,
        ).analyze(_request(), _extracted("后端使用 FastAPI"))
        self.assertEqual("failed", result.status)
        generator.generate.assert_awaited_once()

    async def test_related_path_shorthand_reaches_persistable_detail(self) -> None:
        payload = _semantic().model_dump()
        reference = {"path": "StudentService.java", "relation": "调用业务服务"}
        payload["related_files"] = ["./api.ts", reference]
        client = SimpleNamespace(
            complete_turn=AsyncMock(
                return_value=LLMAssistantTurn(
                    content=json.dumps(payload), finish_reason="stop"
                )
            )
        )
        service = FileSemanticAnalysisService(
            StructuredJsonGenerator(client, max_tokens=16384, timeout_seconds=120),
            max_semantic_input_bytes=1024,
        )

        result = await service.analyze(_request(), _extracted("引用 ./api.ts"))

        self.assertEqual("success", result.status)
        self.assertEqual([{"path": "./api.ts"}, reference], result.detail.related_files)
        self.assertEqual(30, result.detail.file_id)
        client.complete_turn.assert_awaited_once()

    def test_related_files_reject_invalid_types_and_keep_array_limit(self) -> None:
        for value in ([None], [123], [False], [[]], [""], ["   "], "api.ts", None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                FileDetailSemanticOutput.model_validate(
                    {**_semantic().model_dump(), "related_files": value}
                )
        with self.assertRaises(ValidationError):
            FileDetailSemanticOutput.model_validate(
                {**_semantic().model_dump(), "related_files": ["api.ts"] * 51}
            )

    def test_semantic_output_rejects_database_field_overflow(self) -> None:
        payload = _semantic().model_dump()
        payload["module"] = "x" * 129

        with self.assertRaises(ValidationError):
            FileDetailSemanticOutput.model_validate(payload)

    async def test_analyze_rejects_source_over_limit_before_model_call(
        self,
    ) -> None:
        generator = SimpleNamespace(generate=AsyncMock())
        service = FileSemanticAnalysisService(generator, max_semantic_input_bytes=3)

        result = await service.analyze(_request(), _extracted("four"))

        self.assertEqual("failed", result.status)
        self.assertEqual("FILE_DETAIL_SOURCE_TOO_LARGE", result.error_code)
        generator.generate.assert_not_awaited()

    async def test_analyze_records_invalid_structured_response(self) -> None:
        generator = SimpleNamespace(
            generate=AsyncMock(side_effect=ValueError("模型输出被截断"))
        )
        service = FileSemanticAnalysisService(generator, max_semantic_input_bytes=1024)

        result = await service.analyze(
            _request(),
            _extracted("project content"),
        )

        self.assertEqual("failed", result.status)
        self.assertEqual("FILE_DETAIL_MODEL_OUTPUT_INVALID", result.error_code)

    async def test_analyze_assembles_identity_on_server(self) -> None:
        generator = SimpleNamespace(generate=AsyncMock(return_value=_semantic()))
        service = FileSemanticAnalysisService(generator, max_semantic_input_bytes=1024)

        result = await service.analyze(
            _request(),
            _extracted("项目后端使用 FastAPI"),
        )

        self.assertEqual("success", result.status)
        self.assertIsNotNone(result.detail)
        assert result.detail is not None
        self.assertEqual(30, result.detail.file_id)
        self.assertEqual("file-30", result.detail.id)
        self.assertEqual("2.0.0", result.detail.schema_version)
        self.assertEqual("hash", result.detail.content_hash)
        self.assertEqual(
            "后端使用 FastAPI",
            result.detail.rule_candidates[0].text,
        )
        generated_type = generator.generate.await_args.args[1]
        self.assertIs(FileDetailSemanticOutput, generated_type)

    async def test_analyze_returns_safe_output_failure_reason(self) -> None:
        message = "模型结构化输出达到 token 上限（max_tokens=4096），结果不完整"
        generator = SimpleNamespace(
            generate=AsyncMock(side_effect=StructuredOutputError(message))
        )
        service = FileSemanticAnalysisService(generator, max_semantic_input_bytes=1024)

        result = await service.analyze(_request(), _extracted("项目内容"))

        self.assertEqual("FILE_DETAIL_MODEL_OUTPUT_INVALID", result.error_code)
        self.assertEqual(message, result.error_message)
        self.assertIsNone(result.detail)

    async def test_analyze_redacts_credentials_before_model_call(self) -> None:
        generator = SimpleNamespace(generate=AsyncMock(return_value=_semantic()))
        service = FileSemanticAnalysisService(generator, max_semantic_input_bytes=4096)
        secret = "deepseek-secret-value"
        plain_secret = "plain-secret-value"
        json_secret = "json-secret-value"
        github_token = "github_pat_1234567890abcdefghijklmnop"
        slack_token = "xoxp-1234567890-abcdefghijklmnop"
        gitlab_token = "glpat-1234567890abcdefghijkl"
        extracted_content = _extracted(
            f'api_key="{secret}"\n'
            f"password={plain_secret}\n"
            f'{{"client_secret": "{json_secret}"}}\n'
            "database_url=postgres://admin:database-pass@example.com/app\n"
            "Authorization: Bearer abcdefghijklmnop\n"
            f"github token: {github_token}\n"
            f"slack token: {slack_token}\n"
            f"gitlab token: {gitlab_token}"
        )

        result = await service.analyze(_request(), extracted_content)

        prompt = generator.generate.await_args.args[0]
        self.assertNotIn(secret, prompt)
        self.assertNotIn(plain_secret, prompt)
        self.assertNotIn(json_secret, prompt)
        self.assertNotIn("database-pass", prompt)
        self.assertNotIn("abcdefghijklmnop", prompt)
        self.assertNotIn(github_token, prompt)
        self.assertNotIn(slack_token, prompt)
        self.assertNotIn(gitlab_token, prompt)
        self.assertIn("[已脱敏]", prompt)
        assert result.detail is not None
        self.assertEqual(
            "credential_redacted",
            result.detail.sensitive_flags[0]["type"],
        )

    async def test_analyze_blocks_private_key_before_model_call(self) -> None:
        generator = SimpleNamespace(generate=AsyncMock(return_value=_semantic()))
        service = FileSemanticAnalysisService(generator, max_semantic_input_bytes=4096)
        extracted_content = _extracted(
            "-----BEGIN PRIVATE KEY-----\nprivate-material\n-----END PRIVATE KEY-----"
        )

        result = await service.analyze(_request(), extracted_content)

        self.assertEqual("failed", result.status)
        self.assertEqual(
            "FILE_DETAIL_SENSITIVE_CONTENT_BLOCKED",
            result.error_code,
        )
        generator.generate.assert_not_awaited()

    async def test_analyze_blocks_pgp_private_key_before_model_call(self) -> None:
        generator = SimpleNamespace(generate=AsyncMock(return_value=_semantic()))
        service = FileSemanticAnalysisService(generator, max_semantic_input_bytes=4096)
        extracted_content = _extracted(
            "-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
            "private-material\n"
            "-----END PGP PRIVATE KEY BLOCK-----"
        )

        result = await service.analyze(_request(), extracted_content)

        self.assertEqual("failed", result.status)
        self.assertEqual(
            "FILE_DETAIL_SENSITIVE_CONTENT_BLOCKED",
            result.error_code,
        )
        generator.generate.assert_not_awaited()
