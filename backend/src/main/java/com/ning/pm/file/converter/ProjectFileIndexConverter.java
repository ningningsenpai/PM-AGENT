package com.ning.pm.file.converter;

import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.project.context.dto.ProjectIndex;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.Named;
import org.mapstruct.ReportingPolicy;

import java.util.List;

/** ProjectFileIndexConverter 负责将项目文件转换为索引文件条目。 */
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
public interface ProjectFileIndexConverter {

    @Mapping(target = "id", source = "file.id")
    @Mapping(target = "storageUuid", source = "file.storageUuid")
    @Mapping(target = "logicalPath", source = "file.relativePath")
    @Mapping(target = "fileName", source = "file.fileName")
    @Mapping(target = "storageName", source = "storageName")
    @Mapping(target = "minioPath", source = "minioPath")
    @Mapping(target = "sizeBytes", source = "file.sizeBytes")
    @Mapping(target = "contentType", source = "file.contentType")
    @Mapping(target = "status", source = "file.status", qualifiedByName = "statusCode")
    @Mapping(
            target = "quickFingerprint",
            source = "file.quickFingerprint",
            qualifiedByName = "quickFingerprint"
    )
    @Mapping(target = "contentHash", source = "file.contentHash", qualifiedByName = "contentHash")
    @Mapping(target = "updatedAt", source = "file.updatedAt")
    @Mapping(target = "detailRef", source = "file.detailRef")
    @Mapping(target = "analysisVersion", source = "file.analysisVersion")
    @Mapping(target = "module", source = "file.module")
    @Mapping(target = "kind", source = "file.kind")
    @Mapping(target = "fileType", source = "file.fileType")
    @Mapping(target = "language", source = "file.language")
    @Mapping(target = "importance", source = "file.importance")
    @Mapping(target = "summary", source = "file.summary")
    @Mapping(target = "keywords", source = "file.keywords", qualifiedByName = "keywords")
    ProjectIndex.FileEntry toIndexEntry(
            ProjectFile file,
            String storageName,
            String minioPath
    );

    @Named("statusCode")
    default String statusCode(ProjectFileStatus status) {
        return status == null ? null : status.getCode();
    }

    @Named("quickFingerprint")
    default String quickFingerprint(String hash) {
        return prefixHash("qf:sha256:", hash);
    }

    @Named("contentHash")
    default String contentHash(String hash) {
        return prefixHash("sha256:", hash);
    }

    @Named("keywords")
    default List<String> keywords(List<String> keywords) {
        return keywords == null ? List.of() : keywords;
    }

    private String prefixHash(String prefix, String hash) {
        return hash == null || hash.isBlank() ? null : prefix + hash;
    }
}
