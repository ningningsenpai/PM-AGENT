package com.ning.pm.project.service.impl;

import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.project.context.ProjectIndexService;
import com.ning.pm.project.converter.ProjectConverter;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.dto.CreateProjectRequest;
import com.ning.pm.project.dto.ProjectResponse;
import com.ning.pm.project.repository.ProjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * ProjectServiceImplTest 验证项目创建索引初始化和事务回滚补偿。
 *
 * @author ning
 * @date 2026-07-15
 */
@ExtendWith(MockitoExtension.class)
class ProjectServiceImplTest {

    @Mock
    private ProjectMapper projectMapper;
    @Mock
    private ProjectConverter projectConverter;
    @Mock
    private CurrentUserHolder currentUserHolder;
    @Mock
    private ProjectFileMapper projectFileMapper;
    @Mock
    private ProjectIndexService projectIndexService;
    @Mock
    private FileStorageLocationFactory locationFactory;
    @Mock
    private ObjectStorageService objectStorageService;
    @Mock
    private PlatformTransactionManager transactionManager;

    @InjectMocks
    private ProjectServiceImpl service;

    @BeforeEach
    void setUpTransactionSynchronization() {
        TransactionSynchronizationManager.initSynchronization();
    }

    @AfterEach
    void clearTransactionSynchronization() {
        TransactionSynchronizationManager.clearSynchronization();
    }

    @Test
    void rollbackShouldCompensateInitialIndex() {
        CreateProjectRequest request = new CreateProjectRequest("PM-Agent");
        Project project = new Project();
        when(projectConverter.toEntity(request)).thenReturn(project);
        when(currentUserHolder.requireUserId()).thenReturn(1L);
        doAnswer(invocation -> {
            Project inserted = invocation.getArgument(0);
            inserted.setId(10L);
            return 1;
        }).when(projectMapper).insert(any(Project.class));
        when(projectConverter.toResponse(project)).thenReturn(new ProjectResponse(
                10L,
                "PM-Agent",
                project.getStatus(),
                null,
                null
        ));

        ProjectResponse response = service.createProject(request);
        TransactionSynchronization synchronization = TransactionSynchronizationManager
                .getSynchronizations()
                .get(0);
        synchronization.afterCompletion(TransactionSynchronization.STATUS_ROLLED_BACK);

        assertThat(response.id()).isEqualTo(10L);
        verify(projectIndexService).initialize(project);
        verify(projectIndexService).removeInitialIndexWithRetry(project);
    }
}
