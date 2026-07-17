package com.ning.pm.file.batch;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.response.R;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/projects/{projectId}/file-ingest-batches")
@RequiredArgsConstructor
public class ProjectFileIngestBatchController {

    private final ProjectFileIngestBatchService batchService;

    @SaCheckLogin
    @PostMapping
    public R<FileIngestBatchResponse> create(
            @PathVariable Long projectId,
            @RequestHeader("X-Idempotency-Key") String idempotencyKey,
            @Valid @RequestBody CreateFileIngestBatchRequest request
    ) {
        return R.success(batchService.createBatch(projectId, idempotencyKey, request));
    }

    @SaCheckLogin
    @GetMapping("/{batchId}")
    public R<FileIngestBatchResponse> get(
            @PathVariable Long projectId,
            @PathVariable Long batchId
    ) {
        return R.success(batchService.getBatch(projectId, batchId));
    }
}
