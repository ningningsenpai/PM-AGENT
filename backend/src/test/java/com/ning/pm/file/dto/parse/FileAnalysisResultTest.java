package com.ning.pm.file.dto.parse;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * FileAnalysisResultTest 验证 Java 与 Python 文件分析响应的 JSON 契约。
 */
class FileAnalysisResultTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void shouldDeserializeBatchResultAndSnakeCaseDetail() throws Exception {
        String json = """
                [
                  {
                    "projectId": 10,
                    "fileId": 30,
                    "contentHash": "hash",
                    "analysisVersion": "file-detail-v1",
                    "status": "success",
                    "detail": {
                      "id": "file-30",
                      "project_id": 10,
                      "file_id": 30,
                      "schema_version": "1.0.0",
                      "analysis_version": "file-detail-v1",
                      "generated_at": "2026-07-22T10:00:00",
                      "updated_at": "2026-07-22T10:00:00",
                      "storage_uuid": "uuid",
                      "storage_name": "README-uuid.md",
                      "detail_ref": "system/file_details/README-uuid.json",
                      "original_path": "docs/README.md",
                      "minio_path": "project/README-uuid.md",
                      "size_bytes": 10,
                      "content_type": "text/markdown",
                      "content_hash": "hash",
                      "module": "docs",
                      "kind": "documentation",
                      "file_type": "doc",
                      "language": "markdown",
                      "status": "active",
                      "importance": "medium",
                      "summary": "项目说明",
                      "keywords": ["项目文件"],
                      "role": "说明项目结构",
                      "content_slices": [],
                      "related_topics": [],
                      "related_files": [],
                      "risk_flags": [],
                      "sensitive_flags": [],
                      "evidence": [],
                      "previous_versions": [],
                      "parser": {"strategy": "llm_enhanced"}
                    },
                    "errorCode": null,
                    "errorMessage": null
                  }
                ]
                """;

        List<FileAnalysisResult> results = objectMapper.readValue(
                json,
                new TypeReference<>() {
                }
        );

        assertThat(results).hasSize(1);
        assertThat(results.get(0).detail().detailRef())
                .isEqualTo("system/file_details/README-uuid.json");
        assertThat(results.get(0).detail().keywords()).containsExactly("项目文件");
    }
}
