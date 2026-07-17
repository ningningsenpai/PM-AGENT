package com.ning.pm.file.batch;

import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.core.MybatisConfiguration;
import com.baomidou.mybatisplus.core.metadata.TableInfoHelper;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.infrastructure.messaging.outbox.EventOutboxService;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileBatchStageCompletedEvent;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.service.ProjectService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.apache.ibatis.builder.MapperBuilderAssistant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ProjectFileIngestBatchServiceTest {

    @BeforeAll
    static void initTableInfo() {
        MybatisConfiguration configuration = new MybatisConfiguration();
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(configuration, "file-batch-file-test"),
                ProjectFile.class
        );
        TableInfoHelper.initTableInfo(
                new MapperBuilderAssistant(configuration, "file-batch-test"),
                ProjectFileIngestBatch.class
        );
    }

    @Mock
    private ProjectFileIngestBatchMapper batchMapper;
    @Mock
    private ProjectFileMapper fileMapper;
    @Mock
    private ProjectService projectService;
    @Mock
    private EventOutboxService outboxService;

    private ProjectFileIngestBatchService service;

    @BeforeEach
    void setUp() {
        Project project = new Project();
        project.setId(10L);
        lenient().when(projectService.requireOwnedProject(10L)).thenReturn(project);
        service = new ProjectFileIngestBatchService(
                batchMapper,
                fileMapper,
                projectService,
                outboxService
        );
    }

    @Test
    void emptyBatchShouldImmediatelyEnqueueUploadCompletedEvent() {
        when(batchMapper.selectOne(any(Wrapper.class))).thenReturn(null);
        doAnswer(invocation -> {
            ProjectFileIngestBatch batch = invocation.getArgument(0);
            batch.setId(100L);
            return 1;
        }).when(batchMapper).insert(any(ProjectFileIngestBatch.class));

        FileIngestBatchResponse response = service.createBatch(
                10L,
                "batch-key",
                new CreateFileIngestBatchRequest(0)
        );

        assertThat(response.status()).isEqualTo(FileIngestBatchStatus.UPLOAD_COMPLETED);
        verify(outboxService).enqueue(
                anyString(),
                anyString(),
                any(FileBatchStageCompletedEvent.class)
        );
    }

    @Test
    void lastUploadResultShouldOpenAnalysisStageThroughOutbox() {
        ProjectFile file = file();
        ProjectFileIngestBatch batch = batch(FileIngestBatchStatus.UPLOAD_COMPLETED, 2, 2);
        when(fileMapper.update(isNull(), any(Wrapper.class))).thenReturn(1);
        when(batchMapper.update(isNull(), any(Wrapper.class))).thenReturn(1, 1);
        when(batchMapper.selectById(100L)).thenReturn(batch);

        service.recordUploadTerminal(file, true);

        verify(outboxService).enqueue(
                anyString(),
                anyString(),
                any(FileBatchStageCompletedEvent.class)
        );
    }

    @Test
    void duplicateUploadResultShouldNotIncreaseBatchTwice() {
        when(fileMapper.update(isNull(), any(Wrapper.class))).thenReturn(0);

        service.recordUploadTerminal(file(), true);

        verify(batchMapper, never()).update(isNull(), any(Wrapper.class));
        verify(outboxService, never()).enqueue(anyString(), anyString(), any());
    }

    @Test
    void lastAnalysisResultShouldEnqueueFinalIndexEvent() {
        ProjectFile file = file();
        file.setAnalysisCompletionRecorded(false);
        ProjectFileIngestBatch batch = batch(FileIngestBatchStatus.COMPLETED, 1, 1);
        batch.setAnalysisTotal(1);
        batch.setAnalysisCompleted(1);
        batch.setAnalysisSucceeded(1);
        when(fileMapper.update(isNull(), any(Wrapper.class))).thenReturn(1);
        when(batchMapper.update(isNull(), any(Wrapper.class))).thenReturn(1, 1);
        when(batchMapper.selectById(100L)).thenReturn(batch);

        service.recordAnalysisTerminal(file, true);

        verify(outboxService).enqueue(
                anyString(),
                anyString(),
                any(FileBatchStageCompletedEvent.class)
        );
    }

    private ProjectFile file() {
        ProjectFile file = new ProjectFile();
        file.setId(30L);
        file.setProjectId(10L);
        file.setIngestBatchId(100L);
        file.setUploadCompletionRecorded(false);
        return file;
    }

    private ProjectFileIngestBatch batch(
            FileIngestBatchStatus status,
            int total,
            int succeeded
    ) {
        ProjectFileIngestBatch batch = new ProjectFileIngestBatch();
        batch.setId(100L);
        batch.setProjectId(10L);
        batch.setStatus(status);
        batch.setTotalFiles(total);
        batch.setCompletedFiles(total);
        batch.setSucceededFiles(succeeded);
        batch.setFailedFiles(total - succeeded);
        batch.setAnalysisTotal(succeeded);
        batch.setAnalysisCompleted(0);
        batch.setAnalysisSucceeded(0);
        batch.setAnalysisFailed(0);
        return batch;
    }
}
