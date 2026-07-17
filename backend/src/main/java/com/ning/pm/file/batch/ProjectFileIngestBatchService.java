package com.ning.pm.file.batch;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.common.trace.TraceContext;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.infrastructure.messaging.outbox.EventOutboxService;
import com.ning.pm.infrastructure.messaging.rabbitmq.FileMessageTopology;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileBatchStageCompletedEvent;
import com.ning.pm.project.service.ProjectService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 使用数据库计数和单文件终态标记控制上传、解析两个批次闸门。
 */
@Service
@RequiredArgsConstructor
public class ProjectFileIngestBatchService {

    private final ProjectFileIngestBatchMapper batchMapper;
    private final ProjectFileMapper fileMapper;
    private final ProjectService projectService;
    private final EventOutboxService outboxService;

    @Transactional
    public FileIngestBatchResponse createBatch(
            Long projectId,
            String idempotencyKey,
            CreateFileIngestBatchRequest request
    ) {
        projectService.requireOwnedProject(projectId);
        String normalizedKey = normalizeIdempotencyKey(idempotencyKey);
        ProjectFileIngestBatch existing = batchMapper.selectOne(new LambdaQueryWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getProjectId, projectId)
                .eq(ProjectFileIngestBatch::getIdempotencyKey, normalizedKey)
                .last("LIMIT 1"));
        if (existing != null) {
            return toResponse(existing);
        }
        ProjectFileIngestBatch batch = new ProjectFileIngestBatch();
        batch.setProjectId(projectId);
        batch.setIdempotencyKey(normalizedKey);
        batch.setTotalFiles(request.totalFiles());
        batch.setCompletedFiles(0);
        batch.setSucceededFiles(0);
        batch.setFailedFiles(0);
        batch.setAnalysisTotal(0);
        batch.setAnalysisCompleted(0);
        batch.setAnalysisSucceeded(0);
        batch.setAnalysisFailed(0);
        batch.setStatus(request.totalFiles() == 0
                ? FileIngestBatchStatus.UPLOAD_COMPLETED
                : FileIngestBatchStatus.UPLOADING);
        try {
            batchMapper.insert(batch);
        } catch (DuplicateKeyException exception) {
            return toResponse(batchMapper.selectOne(new LambdaQueryWrapper<ProjectFileIngestBatch>()
                    .eq(ProjectFileIngestBatch::getProjectId, projectId)
                    .eq(ProjectFileIngestBatch::getIdempotencyKey, normalizedKey)
                    .last("LIMIT 1")));
        }
        if (request.totalFiles() == 0) {
            enqueueEvent(batch, "upload");
        }
        return toResponse(batch);
    }

    public FileIngestBatchResponse getBatch(Long projectId, Long batchId) {
        projectService.requireOwnedProject(projectId);
        return toResponse(requireBatch(projectId, batchId));
    }

    public ProjectFileIngestBatch requireUploadingBatch(Long projectId, Long batchId) {
        ProjectFileIngestBatch batch = requireBatch(projectId, batchId);
        if (batch.getStatus() != FileIngestBatchStatus.UPLOADING) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID, "文件导入批次已结束上传");
        }
        return batch;
    }

    @Transactional
    public void recordUploadTerminal(ProjectFile file, boolean success) {
        if (file.getIngestBatchId() == null) {
            return;
        }
        int marked = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getIngestBatchId, file.getIngestBatchId())
                .eq(ProjectFile::getUploadCompletionRecorded, false)
                .set(ProjectFile::getUploadCompletionRecorded, true));
        if (marked == 0) {
            return;
        }
        int counted = batchMapper.update(null, new LambdaUpdateWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getId, file.getIngestBatchId())
                .eq(ProjectFileIngestBatch::getProjectId, file.getProjectId())
                .eq(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.UPLOADING)
                .apply("completed_files < total_files")
                .setSql("completed_files = completed_files + 1")
                .setSql(success
                        ? "succeeded_files = succeeded_files + 1"
                        : "failed_files = failed_files + 1"));
        if (counted == 0) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID, "文件导入批次不能继续累计上传结果");
        }
        int completed = batchMapper.update(null, new LambdaUpdateWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getId, file.getIngestBatchId())
                .eq(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.UPLOADING)
                .apply("completed_files = total_files")
                .set(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.UPLOAD_COMPLETED)
                .setSql("analysis_total = succeeded_files"));
        if (completed > 0) {
            enqueueEvent(requireBatch(file.getProjectId(), file.getIngestBatchId()), "upload");
        }
    }

    @Transactional
    public ProjectFileIngestBatch beginAnalysis(Long projectId, Long batchId) {
        batchMapper.update(null, new LambdaUpdateWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getId, batchId)
                .eq(ProjectFileIngestBatch::getProjectId, projectId)
                .eq(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.UPLOAD_COMPLETED)
                .set(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.ANALYZING));
        ProjectFileIngestBatch batch = requireBatch(projectId, batchId);
        if (batch.getAnalysisTotal() == 0 && batch.getStatus() == FileIngestBatchStatus.ANALYZING) {
            int completed = batchMapper.update(null, new LambdaUpdateWrapper<ProjectFileIngestBatch>()
                    .eq(ProjectFileIngestBatch::getId, batchId)
                    .eq(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.ANALYZING)
                    .set(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.COMPLETED));
            if (completed > 0) {
                batch.setStatus(FileIngestBatchStatus.COMPLETED);
                enqueueEvent(batch, "analysis");
            }
        }
        return batch;
    }

    @Transactional
    public void recordAnalysisTerminal(ProjectFile file, boolean success) {
        if (file.getIngestBatchId() == null) {
            return;
        }
        int marked = fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getId, file.getId())
                .eq(ProjectFile::getIngestBatchId, file.getIngestBatchId())
                .eq(ProjectFile::getAnalysisCompletionRecorded, false)
                .set(ProjectFile::getAnalysisCompletionRecorded, true));
        if (marked == 0) {
            return;
        }
        int counted = batchMapper.update(null, new LambdaUpdateWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getId, file.getIngestBatchId())
                .eq(ProjectFileIngestBatch::getProjectId, file.getProjectId())
                .eq(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.ANALYZING)
                .apply("analysis_completed < analysis_total")
                .setSql("analysis_completed = analysis_completed + 1")
                .setSql(success
                        ? "analysis_succeeded = analysis_succeeded + 1"
                        : "analysis_failed = analysis_failed + 1"));
        if (counted == 0) {
            throw new BizException(ErrorCode.FILE_STATUS_INVALID, "文件导入批次不能继续累计解析结果");
        }
        int completed = batchMapper.update(null, new LambdaUpdateWrapper<ProjectFileIngestBatch>()
                .eq(ProjectFileIngestBatch::getId, file.getIngestBatchId())
                .eq(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.ANALYZING)
                .apply("analysis_completed = analysis_total")
                .set(ProjectFileIngestBatch::getStatus, FileIngestBatchStatus.COMPLETED));
        if (completed > 0) {
            enqueueEvent(requireBatch(file.getProjectId(), file.getIngestBatchId()), "analysis");
        }
    }

    private ProjectFileIngestBatch requireBatch(Long projectId, Long batchId) {
        ProjectFileIngestBatch batch = batchMapper.selectById(batchId);
        if (batch == null || !projectId.equals(batch.getProjectId())) {
            throw new BizException(ErrorCode.FILE_NOT_FOUND, "文件导入批次不存在");
        }
        return batch;
    }

    private void enqueueEvent(ProjectFileIngestBatch batch, String stage) {
        FileBatchStageCompletedEvent event = new FileBatchStageCompletedEvent(
                UUID.randomUUID().toString(),
                batch.getId(),
                batch.getProjectId(),
                stage,
                TraceContext.getTraceId(),
                LocalDateTime.now()
        );
        outboxService.enqueue(
                FileMessageTopology.FILE_EXCHANGE,
                "upload".equals(stage)
                        ? FileMessageTopology.UPLOAD_BATCH_COMPLETED_ROUTING_KEY
                        : FileMessageTopology.ANALYSIS_BATCH_COMPLETED_ROUTING_KEY,
                event
        );
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

    private String normalizeIdempotencyKey(String value) {
        if (value == null || value.isBlank() || value.length() > 64) {
            throw new BizException(ErrorCode.PARAM_INVALID, "X-Idempotency-Key长度必须为1到64个字符");
        }
        return value.trim();
    }
}
