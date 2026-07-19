package com.ning.pm.file.service;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.file.domain.ProjectFileUploadRequest;
import com.ning.pm.file.repository.ProjectFileUploadRequestMapper;
import com.ning.pm.project.context.ProjectIndexService;
import com.ning.pm.project.domain.Project;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * 文件上传根请求进入最终态后的唯一业务切入点。
 * 当前只同步重建 index.json；后续接入异步解析时从这里扩展。
 */
@Service
@RequiredArgsConstructor
public class ProjectFileUploadCompletionService {

    private final ProjectIndexService projectIndexService;
    private final ProjectFileUploadRequestMapper uploadRequestMapper;

    public void handleCompleted(Project project, Long uploadRequestId) {
        projectIndexService.rebuild(project);
        uploadRequestMapper.update(null, new LambdaUpdateWrapper<ProjectFileUploadRequest>()
                .eq(ProjectFileUploadRequest::getId, uploadRequestId)
                .isNull(ProjectFileUploadRequest::getIndexRebuiltAt)
                .set(ProjectFileUploadRequest::getIndexRebuiltAt, LocalDateTime.now()));
    }
}
