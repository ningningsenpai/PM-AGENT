package com.ning.pm.file.service;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.file.domain.ProjectFileIngestBatch;
import com.ning.pm.file.dto.batch.FileIngestBatchResponse;
import com.ning.pm.file.repository.ProjectFileIngestBatchMapper;
import com.ning.pm.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

/** 物理上传批次只读查询服务。 */
@Service
@RequiredArgsConstructor
public class ProjectFileIngestBatchService {

    private final ProjectFileIngestBatchMapper batchMapper;
    private final ProjectService projectService;

    public FileIngestBatchResponse getBatch(Long projectId, Long batchId) {
        projectService.requireOwnedProject(projectId);
        return toResponse(requireBatch(projectId, batchId));
    }

    private ProjectFileIngestBatch requireBatch(Long projectId, Long batchId) {
        ProjectFileIngestBatch batch = batchMapper.selectById(batchId);
        if (batch == null || !projectId.equals(batch.getProjectId())) {
            throw new BizException(ErrorCode.FILE_NOT_FOUND, "文件上传批次不存在");
        }
        return batch;
    }

    private FileIngestBatchResponse toResponse(ProjectFileIngestBatch batch) {
        return new FileIngestBatchResponse(
                batch.getId(),
                batch.getProjectId(),
                batch.getTotalFiles(),
                batch.getCompletedFiles(),
                batch.getSucceededFiles(),
                batch.getFailedFiles(),
                batch.getAnalysisTotal(),
                batch.getAnalysisCompleted(),
                batch.getAnalysisSucceeded(),
                batch.getAnalysisFailed(),
                batch.getStatus(),
                batch.getCreatedAt(),
                batch.getUpdatedAt()
        );
    }
}
