package com.ning.pm.file.batch;

import com.ning.pm.file.domain.ProjectFileIngestBatch;
import com.ning.pm.file.dto.batch.FileIngestBatchResponse;
import com.ning.pm.file.enums.FileIngestBatchStatus;
import com.ning.pm.file.repository.ProjectFileIngestBatchMapper;
import com.ning.pm.file.service.ProjectFileIngestBatchService;
import com.ning.pm.project.service.ProjectService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ProjectFileIngestBatchServiceTest {

    @Mock
    private ProjectFileIngestBatchMapper batchMapper;
    @Mock
    private ProjectService projectService;
    @InjectMocks
    private ProjectFileIngestBatchService service;

    @Test
    void shouldReturnPhysicalBatchStatusWithoutMqSideEffect() {
        ProjectFileIngestBatch batch = new ProjectFileIngestBatch();
        batch.setId(100L);
        batch.setProjectId(10L);
        batch.setTotalFiles(2);
        batch.setCompletedFiles(2);
        batch.setSucceededFiles(1);
        batch.setFailedFiles(1);
        batch.setAnalysisTotal(0);
        batch.setAnalysisCompleted(0);
        batch.setAnalysisSucceeded(0);
        batch.setAnalysisFailed(0);
        batch.setStatus(FileIngestBatchStatus.COMPLETED);
        when(batchMapper.selectById(100L)).thenReturn(batch);

        FileIngestBatchResponse response = service.getBatch(10L, 100L);

        assertThat(response.status()).isEqualTo(FileIngestBatchStatus.COMPLETED);
        assertThat(response.succeededFiles()).isEqualTo(1);
        assertThat(response.failedFiles()).isEqualTo(1);
        verify(projectService).requireOwnedProject(10L);
    }
}
