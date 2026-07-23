package com.ning.pm.file.service.storage;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.domain.Project;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

/** FileDetailStorageLocationResolver 统一校验并构建文件详情对象的存储位置。 */
@Component
@RequiredArgsConstructor
public class FileDetailStorageLocationResolver {

    private static final String DETAIL_REF_PREFIX = "system/file_details/";
    private static final String JSON_SUFFIX = ".json";

    private final FileStorageLocationFactory locationFactory;

    public StorageLocation resolve(Project project, String detailRef) {
        validate(detailRef);
        StorageLocation prefix = locationFactory.buildProjectPrefix(
                project.getOwnerUserId(),
                project.getId()
        );
        return new StorageLocation(prefix.bucket(), prefix.objectKey() + detailRef);
    }

    public void validate(String detailRef) {
        if (detailRef == null
                || !detailRef.startsWith(DETAIL_REF_PREFIX)
                || !detailRef.endsWith(JSON_SUFFIX)
                || detailRef.length() <= DETAIL_REF_PREFIX.length() + JSON_SUFFIX.length()
                || detailRef.contains("\\")
                || detailRef.contains("..")
                || detailRef.contains("//")) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "文件详情引用路径不合法");
        }
    }
}
