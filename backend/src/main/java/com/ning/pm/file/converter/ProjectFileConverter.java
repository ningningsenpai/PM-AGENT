package com.ning.pm.file.converter;

import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.CreateProjectFileRequest;
import com.ning.pm.file.dto.ProjectFileResponse;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.ReportingPolicy;

/**
 * ProjectFileConverter 负责文件实体与接口对象之间的字段转换。
 *
 * @author ning
 * @date 2026-07-12
 */
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
public interface ProjectFileConverter {

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "projectId", ignore = true)
    @Mapping(target = "pathHash", ignore = true)
    @Mapping(target = "fileName", ignore = true)
    @Mapping(target = "extension", ignore = true)
    @Mapping(target = "objectKey", ignore = true)
    @Mapping(target = "contentType", ignore = true)
    @Mapping(target = "sizeBytes", ignore = true)
    @Mapping(target = "quickFingerprint", ignore = true)
    @Mapping(target = "contentHash", ignore = true)
    @Mapping(target = "status", ignore = true)
    @Mapping(target = "lockVersion", ignore = true)
    @Mapping(target = "createdAt", ignore = true)
    @Mapping(target = "updatedAt", ignore = true)
    ProjectFile toEntity(CreateProjectFileRequest request);

    ProjectFileResponse toResponse(ProjectFile file);
}
