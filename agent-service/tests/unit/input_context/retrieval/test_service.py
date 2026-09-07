"""输入上下文召回中心测试。"""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from app.core.errors import AppException
from app.infrastructure.storage import StorageLocation, StorageLocationFactory
from app.input_context import (
    InputContextRetrievalService,
    RetrievalQuery,
    UserInputContextService,
    create_default_normalization_service,
)
from app.input_context.normalization import TextNormalizer
from app.input_context.retrieval.snapshot import ProjectSnapshotReader
from app.project_context.file_detail import FileDownloader
from app.project_context.file_detail.extraction import (
    FileContentExtractionService,
    FileContentExtractorFactory,
)

SERVICE_ROOT = Path(__file__).resolve().parents[4]
SYSTEM_ROOT = SERVICE_ROOT / "system"
SOURCE_ROOT = SERVICE_ROOT / "project_test"
OBJECT_PREFIX = "PM-AGENT/0721/0721/"


class FixtureStorage:
    """使用本地夹具模拟只读 MinIO。"""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.read_count = 0
        for path in SYSTEM_ROOT.rglob("*"):
            if path.is_file():
                relative = path.relative_to(SYSTEM_ROOT).as_posix()
                self.objects[("pm-agent", f"{OBJECT_PREFIX}system/{relative}")] = (
                    path.read_bytes()
                )

        index = json.loads((SYSTEM_ROOT / "index.json").read_text(encoding="utf-8"))
        for entry in [*index["project"], *index["user"]]:
            source = SOURCE_ROOT / entry["logical_path"]
            self.objects[("pm-agent", f"{OBJECT_PREFIX}{entry['minio_path']}")] = (
                source.read_bytes()
            )

    def exists(self, location: StorageLocation) -> bool:
        return (location.bucket, location.object_key) in self.objects

    def read_bytes(self, location: StorageLocation) -> bytes:
        self.read_count += 1
        return self.objects[(location.bucket, location.object_key)]


class FixtureNormalization:
    """测试中只保留与生产归一化相同的基础清洗。"""

    def __init__(self) -> None:
        self._normalizer = TextNormalizer()

    def normalize_query(self, text: str, **_kwargs):
        return SimpleNamespace(
            cleaned_text=self._normalizer.normalize_for_matching(text),
            normalized_terms=(),
        )


def _service(storage: FixtureStorage) -> InputContextRetrievalService:
    return InputContextRetrievalService(
        storage,
        StorageLocationFactory(SimpleNamespace(bucket="pm-agent")),
        FixtureNormalization(),
        FileContentExtractionService(
            FileDownloader(),
            FileContentExtractorFactory(),
        ),
    )


def _default_normalization_service(
    storage: FixtureStorage,
) -> InputContextRetrievalService:
    return InputContextRetrievalService(
        storage,
        StorageLocationFactory(SimpleNamespace(bucket="pm-agent")),
        create_default_normalization_service(),
        FileContentExtractionService(
            FileDownloader(),
            FileContentExtractorFactory(),
        ),
    )


class TestInputContextRetrievalService(IsolatedAsyncioTestCase):
    async def test_retrieves_project_stage_from_specification(self) -> None:
        storage = FixtureStorage()

        result = await _service(storage).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(query="项目当前完成度和下一阶段是什么？"),
        )

        self.assertFalse(result.no_evidence)
        self.assertFalse(result.degraded)
        stage_hit = next(
            hit for hit in result.hits if hit.source_id == "development-stage"
        )
        self.assertIn("50%", stage_hit.summary)

    async def test_reads_repository_source_for_exact_sql_question(self) -> None:
        storage = FixtureStorage()

        result = await _service(storage).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(
                query="searchByNameUnsafe 方法为什么存在 SQL 注入风险？给出代码证据",
                evidence_level="source",
            ),
        )

        repository_hit = next(
            hit
            for hit in result.hits
            if hit.logical_path and hit.logical_path.endswith("StudentRepository.java")
        )
        self.assertEqual("source_file", repository_hit.source_type)
        self.assertIn("searchByNameUnsafe", repository_hit.evidence[0].text)
        self.assertIsNotNone(repository_hit.evidence[0].start_line)

    async def test_redacts_plaintext_credentials_from_raw_evidence(self) -> None:
        storage = FixtureStorage()

        result = await _service(storage).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(
                query="application.yml 是否存在明文密码和 API Key？给出配置证据",
                evidence_level="source",
            ),
        )

        evidence_text = "\n".join(
            evidence.text for hit in result.hits for evidence in hit.evidence
        )
        self.assertNotIn("demo_plaintext_password_2026", evidence_text)
        self.assertNotIn("sk-demo-plain-text-key-for-agent-scan", evidence_text)
        self.assertIn("[已脱敏]", evidence_text)

    async def test_raw_evidence_respects_file_and_byte_budget(self) -> None:
        result = await _service(FixtureStorage()).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(
                query="项目代码、SQL 和配置有哪些风险？给出原文证据",
                evidence_level="source",
                limit=8,
            ),
        )

        source_hits = [hit for hit in result.hits if hit.source_type == "source_file"]
        source_bytes = sum(
            len(hit.evidence[0].text.encode("utf-8")) for hit in source_hits
        )
        self.assertLessEqual(len(source_hits), 2)
        self.assertLessEqual(source_bytes, 12 * 1024)

    async def test_reuses_cached_result_and_minio_objects(self) -> None:
        storage = FixtureStorage()
        service = _service(storage)
        request = RetrievalQuery(query="项目使用什么技术栈？")

        first = await service.retrieve(user_id=721, project_id=721, request=request)
        reads_after_first = storage.read_count
        second = await service.retrieve(user_id=721, project_id=721, request=request)

        self.assertEqual(first, second)
        self.assertEqual(reads_after_first, storage.read_count)

    async def test_limits_unique_retrievals_per_request(self) -> None:
        service = _service(FixtureStorage())
        for query in ("完成度", "技术栈", "风险"):
            await service.retrieve(
                user_id=721,
                project_id=721,
                request=RetrievalQuery(query=query),
            )

        with self.assertRaises(AppException):
            await service.retrieve(
                user_id=721,
                project_id=721,
                request=RetrievalQuery(query="第四次不同查询"),
            )

    async def test_pre_retrieval_and_tool_calls_share_the_same_limit(self) -> None:
        service = _default_normalization_service(FixtureStorage())
        await UserInputContextService(service).prepare(
            user_id=721,
            project_id=721,
            raw_query="完成度",
        )
        for query in ("技术栈", "风险"):
            await service.retrieve(
                user_id=721,
                project_id=721,
                request=RetrievalQuery(query=query),
            )

        with self.assertRaises(AppException):
            await service.retrieve(
                user_id=721,
                project_id=721,
                request=RetrievalQuery(query="第四次不同查询"),
            )

    async def test_each_focus_only_returns_its_candidate_provider(self) -> None:
        cases = (
            ("files", "SQL 注入", {"file_detail"}),
            ("specification", "项目按三个阶段推进", {"project_specification"}),
            (
                "memory",
                "轻量单体测试架构",
                {"long_term_memory", "short_term_memory"},
            ),
            ("habits", "按阶段交付", {"user_habit"}),
            ("changes", "项目总索引生成", {"update_journal"}),
        )
        for focus, query, expected_types in cases:
            with self.subTest(focus=focus):
                result = await _service(FixtureStorage()).retrieve(
                    user_id=721,
                    project_id=721,
                    request=RetrievalQuery(
                        query=query,
                        focus=focus,
                        evidence_level="summary",
                    ),
                )
                self.assertTrue(result.hits)
                self.assertTrue(
                    {hit.source_type for hit in result.hits}.issubset(expected_types)
                )

    async def test_missing_project_index_returns_no_evidence(self) -> None:
        storage = FixtureStorage()
        result = await _service(storage).retrieve(
            user_id=722,
            project_id=721,
            request=RetrievalQuery(query="项目当前完成度"),
        )

        self.assertTrue(result.no_evidence)
        self.assertTrue(result.degraded)
        self.assertIn("system/index.json", result.warnings[-1])
        self.assertEqual(0, storage.read_count)

    async def test_mismatched_index_identity_does_not_read_project_objects(
        self,
    ) -> None:
        storage = FixtureStorage()
        locations = StorageLocationFactory(SimpleNamespace(bucket="pm-agent"))
        foreign_prefix = locations.project_prefix(722, 721).object_key
        storage.objects[("pm-agent", f"{foreign_prefix}system/index.json")] = (
            SYSTEM_ROOT / "index.json"
        ).read_bytes()

        result = await _service(storage).retrieve(
            user_id=722,
            project_id=721,
            request=RetrievalQuery(query="项目当前完成度"),
        )

        self.assertTrue(result.no_evidence)
        self.assertTrue(result.degraded)
        self.assertTrue(any("身份与当前对话不一致" in item for item in result.warnings))
        self.assertEqual(1, storage.read_count)

    async def test_default_normalization_uses_versioned_lexicons(self) -> None:
        result = await _default_normalization_service(FixtureStorage()).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(query="项目技术栈"),
        )

        self.assertFalse(result.no_evidence)
        self.assertFalse(result.degraded)

    async def test_prepared_input_context_never_reads_raw_source(self) -> None:
        service = _default_normalization_service(FixtureStorage())

        context = await UserInputContextService(service).prepare(
            user_id=721,
            project_id=721,
            raw_query="searchByNameUnsafe 的代码证据是什么？",
            trace_id="trace-pre",
        )

        self.assertIsNotNone(context.normalization)
        self.assertFalse(context.retrieval.no_evidence)
        self.assertTrue(
            all(hit.source_type != "source_file" for hit in context.retrieval.hits)
        )

    async def test_prepared_input_context_preserves_long_raw_query(self) -> None:
        service = _default_normalization_service(FixtureStorage())
        raw_query = "项目风险" * 501

        context = await UserInputContextService(service).prepare(
            user_id=721,
            project_id=721,
            raw_query=raw_query,
        )

        self.assertEqual(raw_query, context.raw_query)
        self.assertEqual(2000, len(context.retrieval.query))

    async def test_prepared_context_can_include_bounded_verbatim_source(self):
        context = await UserInputContextService(
            _default_normalization_service(FixtureStorage())
        ).prepare(
            user_id=721,
            project_id=721,
            raw_query="searchByNameUnsafe 的代码证据是什么？",
            include_source=True,
        )
        source = [
            evidence
            for hit in context.retrieval.hits
            for evidence in hit.evidence
            if evidence.kind == "source"
        ]
        self.assertTrue(source)
        self.assertLessEqual(len(source), 2)
        self.assertLessEqual(sum(len(item.text.encode()) for item in source), 12 * 1024)
        self.assertTrue(any("searchByNameUnsafe" in item.text for item in source))
        self.assertTrue(
            any(
                evidence.kind == "summary"
                for hit in context.retrieval.hits
                for evidence in hit.evidence
            )
        )

    async def test_invalid_file_detail_falls_back_to_index_summary(self) -> None:
        storage = FixtureStorage()
        index = json.loads((SYSTEM_ROOT / "index.json").read_text(encoding="utf-8"))
        entry = next(
            item
            for item in index["project"]
            if item["logical_path"].endswith("StudentRepository.java")
        )
        storage.objects[("pm-agent", f"{OBJECT_PREFIX}{entry['detail_ref']}")] = b"{"

        result = await _service(storage).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(query="StudentRepository SQL 注入"),
        )

        hit = next(
            item
            for item in result.hits
            if item.logical_path
            and item.logical_path.endswith("StudentRepository.java")
        )
        self.assertEqual(entry["summary"], hit.summary)
        self.assertTrue(any("文件详情不可用" in item for item in result.warnings))

    async def test_private_key_source_is_blocked_and_detail_is_retained(self) -> None:
        storage = FixtureStorage()
        index = json.loads((SYSTEM_ROOT / "index.json").read_text(encoding="utf-8"))
        entry = next(
            item
            for item in index["project"]
            if item["logical_path"].endswith("StudentRepository.java")
        )
        storage.objects[("pm-agent", f"{OBJECT_PREFIX}{entry['minio_path']}")] = (
            b"-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"
        )
        raw = storage.objects[("pm-agent", f"{OBJECT_PREFIX}{entry['minio_path']}")]
        entry["content_hash"] = "sha256:" + hashlib.sha256(raw).hexdigest()
        storage.objects[("pm-agent", f"{OBJECT_PREFIX}system/index.json")] = json.dumps(
            index
        ).encode()
        detail_key = ("pm-agent", f"{OBJECT_PREFIX}{entry['detail_ref']}")
        detail = json.loads(storage.objects[detail_key])
        detail["content_hash"] = entry["content_hash"]
        storage.objects[detail_key] = json.dumps(detail).encode()

        result = await _service(storage).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(
                query="StudentRepository SQL 注入代码证据",
                evidence_level="source",
            ),
        )

        hit = next(
            item
            for item in result.hits
            if item.logical_path
            and item.logical_path.endswith("StudentRepository.java")
        )
        self.assertEqual("file_detail", hit.source_type)
        self.assertTrue(any("敏感内容" in item for item in result.warnings))

    async def test_raw_evidence_enrichment_does_not_change_relevance_score(
        self,
    ) -> None:
        service = _service(FixtureStorage())
        query = "searchByNameUnsafe 方法为什么存在 SQL 注入风险？"
        summary = await service.retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(query=query, evidence_level="summary"),
        )
        source = await service.retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(query=query, evidence_level="source"),
        )

        summary_hit = next(
            hit
            for hit in summary.hits
            if hit.logical_path and hit.logical_path.endswith("StudentRepository.java")
        )
        source_hit = next(
            hit for hit in source.hits if hit.logical_path == summary_hit.logical_path
        )
        self.assertEqual(summary_hit.score, source_hit.score)
        self.assertEqual("source_file", source_hit.source_type)

    def test_snapshot_rejects_unsafe_object_references(self) -> None:
        for value in ("../secret.txt", "/system/index.json", "system\\index.json"):
            with self.assertRaises(ValueError):
                ProjectSnapshotReader._safe_relative_path(value)

    async def test_fixture_risk_recall_at_five_covers_r01_to_r07(self) -> None:
        cases = (
            ("R-01 明文凭据风险在哪里？", ("application.yml", "开发文档.md")),
            ("R-02 自增主键有什么风险？", ("schema.sql", "开发文档.md")),
            (
                "R-03 SQL 注入风险在哪里？",
                ("StudentRepository.java", "risk-parameterized-sql"),
            ),
            ("R-04 CORS 风险在哪里？", ("WebConfig.java", "risk-restrict-cors")),
            (
                "R-05 鉴权和幂等风险在哪里？",
                ("StudentController.java", "risk-auth-idempotency"),
            ),
            (
                "R-06 电话邮箱个人信息暴露风险在哪里？",
                ("Student.java", "risk-mask-student-pii"),
            ),
            (
                "R-07 自动化测试覆盖有什么不足？",
                ("StudentControllerTest.java", "risk-complete-test-coverage"),
            ),
        )
        recalled = 0
        for query, expected_sources in cases:
            result = await _service(FixtureStorage()).retrieve(
                user_id=721,
                project_id=721,
                request=RetrievalQuery(query=query),
            )
            searchable = "\n".join(
                " ".join(
                    filter(
                        None,
                        (
                            hit.source_id,
                            hit.logical_path,
                            hit.title,
                            hit.summary,
                        ),
                    )
                )
                for hit in result.hits[:5]
            )
            if any(source in searchable for source in expected_sources):
                recalled += 1

        self.assertEqual(len(cases), recalled)

    async def test_new_bare_detail_hash_matches_prefixed_index(self):
        storage = FixtureStorage()
        for key, raw in list(storage.objects.items()):
            if "/system/file_details/" in key[1]:
                detail = json.loads(raw)
                detail["content_hash"] = detail["content_hash"].removeprefix("sha256:")
                storage.objects[key] = json.dumps(detail).encode()
        result = await _service(storage).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(
                query="StudentRepository SQL 注入",
                focus="files",
                evidence_level="summary",
            ),
        )
        self.assertFalse(
            any("身份或内容哈希" in warning for warning in result.warnings)
        )
        hit = next(
            item
            for item in result.hits
            if item.logical_path
            and item.logical_path.endswith("StudentRepository.java")
        )
        self.assertTrue(any(item.start_line is not None for item in hit.evidence))

    async def test_changed_source_does_not_become_verified_evidence(self):
        storage = FixtureStorage()
        index = json.loads((SYSTEM_ROOT / "index.json").read_text(encoding="utf-8"))
        entry = next(
            item
            for item in index["project"]
            if item["logical_path"].endswith("StudentRepository.java")
        )
        storage.objects[("pm-agent", f"{OBJECT_PREFIX}{entry['minio_path']}")] = (
            b"unindexed-source-change"
        )
        result = await _service(storage).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(
                query="StudentRepository SQL 注入", evidence_level="source"
            ),
        )
        self.assertTrue(any("原文件内容哈希" in warning for warning in result.warnings))
        hit = next(
            item for item in result.hits if item.logical_path == entry["logical_path"]
        )
        self.assertNotEqual("source_file", hit.source_type)
        self.assertNotIn("unindexed-source-change", str(hit.evidence))

    async def test_different_detail_hash_is_still_rejected(self):
        storage = FixtureStorage()
        index = json.loads((SYSTEM_ROOT / "index.json").read_text(encoding="utf-8"))
        entry = next(
            item
            for item in index["project"]
            if item["logical_path"].endswith("StudentRepository.java")
        )
        key = ("pm-agent", f"{OBJECT_PREFIX}{entry['detail_ref']}")
        detail = json.loads(storage.objects[key])
        detail["content_hash"] = "0" * 64
        storage.objects[key] = json.dumps(detail).encode()
        result = await _service(storage).retrieve(
            user_id=721,
            project_id=721,
            request=RetrievalQuery(
                query="StudentRepository SQL 注入",
                focus="files",
                evidence_level="summary",
            ),
        )
        self.assertTrue(any("身份或内容哈希" in warning for warning in result.warnings))
        hit = next(
            item for item in result.hits if item.logical_path == entry["logical_path"]
        )
        self.assertEqual(entry["summary"], hit.evidence[0].text)
