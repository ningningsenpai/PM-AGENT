package com.ning.pm.file.service;

import com.ning.pm.file.dto.CreateProjectFileRequest;
import com.ning.pm.file.dto.FileReadUrlResponse;
import com.ning.pm.file.dto.OverwriteProjectFileRequest;
import com.ning.pm.file.dto.ProjectFileResponse;
import com.ning.pm.file.dto.UpdateProjectFilePathRequest;
import com.ning.pm.file.enums.FileBusinessType;

import java.util.List;

public interface ProjectFileService {

    ProjectFileResponse createFile(Long projectId, String idempotencyKey, CreateProjectFileRequest request);

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
