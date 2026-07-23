package com.ning.pm.file.service.validation;

import com.ning.pm.file.dto.parse.FileAnalysisRequest;
import com.ning.pm.file.dto.parse.FileAnalysisResult;
import com.ning.pm.file.dto.parse.FileDetail;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** FileAnalysisResultValidatorTest 验证文件分析批量结果的身份和状态约束。 */
class FileAnalysisResultValidatorTest {

    private final FileAnalysisResultValidator validator = new FileAnalysisResultValidator();

    @Test
    void validateShouldAcceptMatchingSuccessResult() {
        FileAnalysisRequest request = request(30L, "hash-30");
        FileAnalysisResult result = new FileAnalysisResult(
                10L,
                30L,
                "hash-30",
                "file-detail-v1",
                "success",
                detail(request),
                null,
                null
        );

        assertThatCode(() -> validator.validate(10L, List.of(request), List.of(result)))
                .doesNotThrowAnyException();
    }

    @Test
    void validateShouldRejectDuplicateResultFileId() {
        List<FileAnalysisRequest> requests = List.of(
                request(30L, "hash-30"),
                request(31L, "hash-31")
        );
        FileAnalysisResult result = failedResult(30L, "hash-30");

        assertThatThrownBy(() -> validator.validate(10L, requests, List.of(result, result)))
                .hasMessageContaining("空值或重复文件");
    }

    @Test
    void validateShouldRejectSuccessResultWithoutDetail() {
        FileAnalysisRequest request = request(30L, "hash-30");
        FileAnalysisResult result = new FileAnalysisResult(
                10L,
                30L,
                "hash-30",
                "file-detail-v1",
                "success",
                null,
                null,
                null
        );

        assertThatThrownBy(() -> validator.validate(10L, List.of(request), List.of(result)))
                .hasMessageContaining("身份字段不一致");
    }

    private FileAnalysisRequest request(Long fileId, String contentHash) {
        String storageName = "README-" + fileId + ".md";
        return new FileAnalysisRequest(
                1L,
                10L,
                "project",
                fileId,
                "README.md",
                "http://localhost/file",
                "md",
                "uuid-" + fileId,
                storageName,
                "system/file_details/README-" + fileId + ".json",
                "docs/README.md",
                "project/" + storageName,
                100L,
                "text/markdown",
                contentHash,
                "file-detail-v1"
        );
    }

    private FileAnalysisResult failedResult(Long fileId, String contentHash) {
        return new FileAnalysisResult(
                10L,
                fileId,
                contentHash,
                "file-detail-v1",
                "failed",
                null,
                "PARSE_FAILED",
                "解析失败"
        );
    }

    private FileDetail detail(FileAnalysisRequest request) {
        return new FileDetail(
                "file-" + request.fileId(),
                request.projectId(),
                request.fileId(),
                "1.0.0",
                request.analysisVersion(),
                "2026-07-23T10:00:00",
                "2026-07-23T10:00:00",
                request.storageUuid(),
                request.storageName(),
                request.detailRef(),
                request.originalPath(),
                request.minioPath(),
                request.sizeBytes(),
                request.contentType(),
                request.contentHash(),
                "docs",
                "documentation",
                "doc",
                "markdown",
                "active",
                "medium",
                "项目说明",
                List.of("项目文件"),
                "说明项目结构",
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                null
        );
    }
}
