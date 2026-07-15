package com.ning.pm.project.context;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.project.context.dto.ProjectIndex;
import com.ning.pm.project.domain.Project;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * ProjectIndexServiceTest 验证初始索引的有限重试和统一错误码。
 *
 * @author ning
 * @date 2026-07-15
 */
@ExtendWith(MockitoExtension.class)
class ProjectIndexServiceTest {

    @Mock
    private ProjectFileMapper fileMapper;
    @Mock
    private ProjectIndexFactory indexFactory;
    @Mock
    private ProjectIndexWriter indexWriter;
    @Mock
    private ObjectStorageService objectStorageService;

    @InjectMocks
    private ProjectIndexService service;

    @Test
    void initializeShouldStopAfterThreeFailures() {
        Project project = project();
        ProjectIndex index = org.mockito.Mockito.mock(ProjectIndex.class);
        when(indexFactory.createInitialIndex(project)).thenReturn(index);
        doThrow(new SystemException(ErrorCode.FILE_STORAGE_ERROR))
                .when(indexWriter)
                .writeIndex(1L, 10L, index);

        assertThatThrownBy(() -> service.initialize(project))
                .isInstanceOf(SystemException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.PROJECT_INDEX_INIT_FAILED);

        verify(indexWriter, times(3)).writeIndex(1L, 10L, index);
    }

    private Project project() {
        Project project = new Project();
        project.setId(10L);
        project.setOwnerUserId(1L);
        project.setProjectName("PM-Agent");
        return project;
    }
}
