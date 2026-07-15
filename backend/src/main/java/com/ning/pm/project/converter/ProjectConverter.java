package com.ning.pm.project.converter;

import com.ning.pm.project.domain.Project;
import com.ning.pm.project.dto.CreateProjectRequest;
import com.ning.pm.project.dto.ProjectResponse;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.ReportingPolicy;

/**
 * ProjectConverter 负责项目实体与接口对象之间的字段转换。
 *
 * @author ning
 * @date 2026-07-12
 */
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
public interface ProjectConverter {

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "ownerUserId", ignore = true)
    @Mapping(target = "status", ignore = true)
    @Mapping(target = "createdAt", ignore = true)
    @Mapping(target = "updatedAt", ignore = true)
    Project toEntity(CreateProjectRequest request);

    ProjectResponse toResponse(Project project);
}
