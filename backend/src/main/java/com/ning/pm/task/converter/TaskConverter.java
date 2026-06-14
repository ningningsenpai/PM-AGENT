package com.ning.pm.task.converter;

import com.ning.pm.task.domain.Task;
import com.ning.pm.task.dto.CreateTaskRequest;
import com.ning.pm.task.dto.TaskResponse;
import com.ning.pm.task.dto.UpdateTaskRequest;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.MappingTarget;
import org.mapstruct.ReportingPolicy;

/**
 * TaskConverter 负责任务实体与接口对象之间的字段转换。
 *
 * @author ning
 * @date 2026-06-10
 */
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
public interface TaskConverter {

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "tenantId", ignore = true)
    @Mapping(target = "createdBy", ignore = true)
    @Mapping(target = "createdAt", ignore = true)
    @Mapping(target = "updatedBy", ignore = true)
    @Mapping(target = "updatedAt", ignore = true)
    @Mapping(target = "deleted", ignore = true)
    @Mapping(target = "requirementId", ignore = true)
    @Mapping(target = "iterationId", ignore = true)
    @Mapping(target = "status", ignore = true)
    @Mapping(target = "actualHours", ignore = true)
    Task toEntity(CreateTaskRequest request);

    TaskResponse toResponse(Task task);

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "tenantId", ignore = true)
    @Mapping(target = "createdBy", ignore = true)
    @Mapping(target = "createdAt", ignore = true)
    @Mapping(target = "updatedBy", ignore = true)
    @Mapping(target = "updatedAt", ignore = true)
    @Mapping(target = "deleted", ignore = true)
    @Mapping(target = "projectId", ignore = true)
    @Mapping(target = "requirementId", ignore = true)
    @Mapping(target = "iterationId", ignore = true)
    @Mapping(target = "status", ignore = true)
    void updateEntity(@MappingTarget Task task, UpdateTaskRequest request);
}
