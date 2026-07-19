package com.ning.pm.file.service;

import com.ning.pm.file.dto.file.FileReadUrlResponse;
import com.ning.pm.file.dto.file.OverwriteProjectFileRequest;
import com.ning.pm.file.dto.file.ProjectFileResponse;
import com.ning.pm.file.dto.file.UpdateProjectFilePathRequest;
import com.ning.pm.file.enums.FileBusinessType;

import java.util.List;

public interface ProjectFileService {

    ProjectFileResponse overwriteContent(
            Long projectId,
            Long fileId,
            String idempotencyKey,
            OverwriteProjectFileRequest request
    );

    ProjectFileResponse updatePath(Long projectId, Long fileId, UpdateProjectFilePathRequest request);

    List<ProjectFileResponse> listFiles(Long projectId, FileBusinessType businessCode);

    FileReadUrlResponse createReadUrl(Long projectId, Long fileId);

    void deleteFile(Long projectId, Long fileId, Integer lockVersion);
}
