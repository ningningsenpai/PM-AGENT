package com.ning.pm.file.converter;

import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.file.ProjectFileResponse;
import org.mapstruct.Mapper;
import org.mapstruct.ReportingPolicy;

/** ProjectFileConverter 负责文件实体与接口响应之间的字段转换。 */
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
public interface ProjectFileConverter {

    ProjectFileResponse toResponse(ProjectFile file);
}
