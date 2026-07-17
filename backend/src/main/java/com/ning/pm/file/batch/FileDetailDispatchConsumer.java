package com.ning.pm.file.batch;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.file.analysis.FileDetailTaskPublisher;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.file.enums.ProjectFileAnalysisStatus;
import com.ning.pm.file.enums.ProjectFileUploadStatus;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.infrastructure.messaging.rabbitmq.FileMessageTopology;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileBatchStageCompletedEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * 上传批次完成后批量查询成功文件，并为 Python 逐个生成短期读取任务。
 */
@Component
@RequiredArgsConstructor
public class FileDetailDispatchConsumer {

    private final ProjectFileIngestBatchService batchService;
    private final ProjectFileMapper fileMapper;
    private final FileDetailTaskPublisher taskPublisher;

    @RabbitListener(queues = FileMessageTopology.FILE_DETAIL_DISPATCH_QUEUE)
    public void consume(FileBatchStageCompletedEvent event) {
        ProjectFileIngestBatch batch = batchService.beginAnalysis(event.projectId(), event.batchId());
        if (batch.getAnalysisTotal() == 0 || batch.getStatus() == FileIngestBatchStatus.COMPLETED) {
            return;
        }
        fileMapper.update(null, new LambdaUpdateWrapper<ProjectFile>()
                .eq(ProjectFile::getProjectId, event.projectId())
                .eq(ProjectFile::getIngestBatchId, event.batchId())
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .in(ProjectFile::getAnalysisStatus,
                        ProjectFileAnalysisStatus.PENDING,
                        ProjectFileAnalysisStatus.RETRYING)
                .set(ProjectFile::getAnalysisStatus, ProjectFileAnalysisStatus.PROCESSING));
        List<ProjectFile> files = fileMapper.selectList(new LambdaQueryWrapper<ProjectFile>()
                .eq(ProjectFile::getProjectId, event.projectId())
                .eq(ProjectFile::getIngestBatchId, event.batchId())
                .eq(ProjectFile::getStatus, ProjectFileStatus.ACTIVE)
                .eq(ProjectFile::getUploadStatus, ProjectFileUploadStatus.SUCCESS)
                .notIn(ProjectFile::getAnalysisStatus,
                        ProjectFileAnalysisStatus.SUCCESS,
                        ProjectFileAnalysisStatus.FAILED)
                .orderByAsc(ProjectFile::getId));
        files.forEach(taskPublisher::publish);
    }
}
