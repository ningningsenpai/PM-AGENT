package com.ning.pm.project.context;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.context.dto.ProjectIndex;
import com.ning.pm.project.context.json.ProjectIndexJsonCodec;
import com.ning.pm.project.domain.SystemFilePath;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

/**
 * ProjectIndexWriter 校验并整体覆盖固定 system/index.json，不提供公开写入入口。
 *
 * @author ning
 * @date 2026-07-15
 */
@Component
@RequiredArgsConstructor
public class ProjectIndexWriter {

    private final ProjectIndexJsonCodec projectIndexJsonCodec;
    private final ObjectStorageService objectStorageService;
    private final FileStorageLocationFactory locationFactory;

    public void writeIndex(Long userId, Long projectId, ProjectIndex index) {
        validate(index);
        objectStorageService.putObject(
                indexLocation(userId, projectId),
                projectIndexJsonCodec.serialize(index),
                "application/json"
        );
    }

    public StorageLocation indexLocation(Long userId, Long projectId) {
        return locationFactory.buildSystemFile(userId, projectId, SystemFilePath.INDEX);
    }

    private void validate(ProjectIndex index) {
        if (index == null
                || index.projectId() == null
                || index.ownerUserId() == null
                || index.storage() == null
                || index.summary() == null
                || index.project() == null
                || index.user() == null
                || index.uploadFailures() == null
                || index.system() == null) {
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_WRITE_FAILED,
                    "项目上下文索引结构不完整"
            );
        }
    }
}
