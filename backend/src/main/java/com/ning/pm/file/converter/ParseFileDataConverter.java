package com.ning.pm.file.converter;

import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.parse.FileAnalysisRequest;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.ReportingPolicy;

@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
public interface ParseFileDataConverter {

    @Mapping(target = "userId", source = "userId")
    @Mapping(target = "fileId", source = "projectFile.id")
    @Mapping(target = "business", source = "projectFile.businessCode.code")
    @Mapping(target = "filename", source = "projectFile.fileName")
    @Mapping(target = "fileUrl", source = "fileUrl")
    @Mapping(target = "fileType", source = "projectFile.extension")
    @Mapping(target = "detailRef", source = "detailRef")
    @Mapping(target = "originalPath", source = "projectFile.relativePath")
    @Mapping(target = "analysisVersion", source = "analysisVersion")
    FileAnalysisRequest toFileAnalysisRequest(
            ProjectFile projectFile,
            Long userId,
            String fileUrl,
            String detailRef,
            String analysisVersion
    );
}