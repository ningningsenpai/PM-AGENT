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
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.transaction.PlatformTransactionManager;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.project.domain.ProjectStatus;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.doThrow;

/**
 * ProjectServiceImplTest 验证项目创建时数据库事务与 MinIO 初始化分离。
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
    @Mock
    private ProjectInitializationPersistenceService initializationPersistenceService;

    @InjectMocks
    private ProjectServiceImpl service;

    @Test
    void createShouldInitializeIndexOutsidePersistenceStepAndActivateProject() {
        CreateProjectRequest request = new CreateProjectRequest("PM-Agent");
        Project project = new Project();
        when(projectConverter.toEntity(request)).thenReturn(project);
        when(currentUserHolder.requireUserId()).thenReturn(1L);
        doAnswer(invocation -> {
            Project inserted = invocation.getArgument(0);
            inserted.setId(10L);
            return null;
        }).when(initializationPersistenceService).insertInitializing(any(Project.class));
        when(initializationPersistenceService.markInitToActive(10L)).thenReturn(true);
        when(projectConverter.toResponse(project)).thenReturn(new ProjectResponse(
                10L,
                "PM-Agent",
                project.getStatus(),
                null,
                null
        ));

        ProjectResponse response = service.createProject(request);

        assertThat(response.id()).isEqualTo(10L);
        assertThat(project.getStatus()).isEqualTo(ProjectStatus.ACTIVE);
        verify(initializationPersistenceService).insertInitializing(project);
        verify(projectIndexService).initialize(project);
        verify(initializationPersistenceService).markInitToActive(10L);
    }

    @Test
    void initializationFailureShouldPersistFailedStatus() {
        CreateProjectRequest request = new CreateProjectRequest("PM-Agent");
        Project project = new Project();
        project.setId(10L);
        when(projectConverter.toEntity(request)).thenReturn(project);
        when(currentUserHolder.requireUserId()).thenReturn(1L);
        doThrow(new SystemException(ErrorCode.PROJECT_INDEX_INIT_FAILED))
                .when(projectIndexService).initialize(project);

        assertThatThrownBy(() -> service.createProject(request))
                .isInstanceOf(SystemException.class);

        verify(initializationPersistenceService).deleteProject(10L);
    }

    @Test
    void retryFailedInitializationShouldRecreateIndexBeforeActivatingProject() {
        CreateProjectRequest request = new CreateProjectRequest("PM-Agent");
        Project project = new Project();
        project.setId(10L);
        project.setProjectName("PM-Agent");
        project.setOwnerUserId(1L);
        project.setStatus(ProjectStatus.INIT_FAILED);
        when(currentUserHolder.requireUserId()).thenReturn(1L);
        when(initializationPersistenceService.checkProject(1L, "PM-Agent")).thenReturn(project);
        when(initializationPersistenceService.markInitFailedToActive(10L)).thenReturn(true);
        when(projectConverter.toResponse(project)).thenReturn(new ProjectResponse(
                10L,
                "PM-Agent",
                ProjectStatus.ACTIVE,
                null,
                null
        ));

        ProjectResponse response = service.createProject(request);

        assertThat(response.status()).isEqualTo(ProjectStatus.ACTIVE);
        verify(projectIndexService).initialize(project);
        verify(initializationPersistenceService).markInitFailedToActive(10L);
    }
}
