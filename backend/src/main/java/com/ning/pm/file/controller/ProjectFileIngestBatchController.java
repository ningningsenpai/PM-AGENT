package com.ning.pm.file.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.response.R;
import com.ning.pm.file.dto.batch.FileIngestBatchResponse;
import com.ning.pm.file.dto.batch.ProjectFileUploadResponse;
import com.ning.pm.file.dto.batch.ProjectUploadBatchRequest;
import com.ning.pm.file.dto.batch.ProjectUploadManifestRequest;
import com.ning.pm.file.service.ProjectFileBatchUploadService;
import com.ning.pm.file.service.ProjectFileIngestBatchService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

@RestController
@RequestMapping("/api/v1/projects/{projectId}/file-ingest-batches")
@RequiredArgsConstructor
public class ProjectFileIngestBatchController {

    private final ProjectFileBatchUploadService batchUploadService;
    private final ProjectFileIngestBatchService batchService;

    @SaCheckLogin
    @PostMapping(path = "/concurrent-uploads", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public R<ProjectFileUploadResponse> uploadBatch(
            @PathVariable Long projectId,
            @RequestHeader("X-Idempotency-Key") String idempotencyKey,
            @Valid @RequestPart("manifest") ProjectUploadManifestRequest manifest,
            @Valid @RequestPart("batch") ProjectUploadBatchRequest batch,
            @RequestPart("files") List<MultipartFile> files
    ) {
        return R.success(batchUploadService.uploadBatch(
                projectId,
                idempotencyKey,
                manifest,
                batch,
                files
        ));
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
