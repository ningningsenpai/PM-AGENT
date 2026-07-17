package com.ning.pm.file.analysis;

import com.ning.pm.common.response.R;
import com.ning.pm.file.analysis.dto.FileAnalysisResultRequest;
import com.ning.pm.file.analysis.dto.InternalFileReadUrlResponse;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Java 与 Python Agent 之间的文件解析内部接口。
 */
@RestController
@RequestMapping("/api/v1/agent/projects/{projectId}/files/{fileId}")
@RequiredArgsConstructor
public class FileDetailAnalysisController {

    private final InternalServiceAuthenticator authenticator;
    private final FileDetailAnalysisService analysisService;

    @GetMapping("/read-url")
    public R<InternalFileReadUrlResponse> createReadUrl(
            @PathVariable Long projectId,
            @PathVariable Long fileId,
            @RequestHeader("X-Internal-Service-Token") String internalToken
    ) {
        authenticator.requireValidToken(internalToken);
        return R.success(analysisService.createReadUrl(projectId, fileId));
    }

    @PutMapping("/analysis-result")
    public R<Void> saveResult(
            @PathVariable Long projectId,
            @PathVariable Long fileId,
            @RequestHeader("X-Internal-Service-Token") String internalToken,
            @RequestHeader("X-Idempotency-Key") String idempotencyKey,
            @Valid @RequestBody FileAnalysisResultRequest request
    ) {
        authenticator.requireValidToken(internalToken);
        analysisService.saveResult(projectId, fileId, idempotencyKey, request);
        return R.success(null);
    }
}
