package com.ning.pm.file.service;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.domain.SystemFilePath;
import org.springframework.stereotype.Component;

import java.text.Normalizer;
import java.util.Locale;
import java.util.UUID;

/**
 * FileStorageLocationFactory 统一生成项目文件、用户文件和受控系统文件的 MinIO 位置。
 *
 * @author ning
 * @date 2026-07-15
 */
@Component
public class FileStorageLocationFactory {

    private static final String ROOT_PREFIX = "PM-AGENT";
    private static final String STORAGE_UUID_PATTERN = "[0-9a-f]{16}";

    public String createStorageUuid() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 16);
    }

    public StorageLocation buildProjectFile(
            Long userId,
            Long projectId,
            String fileName,
            String storageUuid
    ) {
        return buildRegularFile(userId, projectId, FileBusinessType.PROJECT, fileName, storageUuid);
    }

    public StorageLocation buildUserFile(
            Long userId,
            Long projectId,
            String fileName,
            String storageUuid
    ) {
        return buildRegularFile(userId, projectId, FileBusinessType.USER, fileName, storageUuid);
    }

    public StorageLocation buildRegularFile(
            Long userId,
            Long projectId,
            FileBusinessType businessType,
            String fileName,
            String storageUuid
    ) {
        validateId(userId, "用户ID");
        validateId(projectId, "项目ID");
        if (businessType == null || businessType == FileBusinessType.SYSTEM) {
            throw new BizException(ErrorCode.SYSTEM_FILE_ACCESS_DENIED);
        }
        String storageName = buildStorageName(fileName, storageUuid);
        return new StorageLocation(
                StorageLocation.PROJECT_BUCKET,
                "%s/%d/%d/%s/%s".formatted(
                        ROOT_PREFIX,
                        userId,
                        projectId,
                        businessType.getCode(),
                        storageName
                )
        );
    }

    public StorageLocation buildSystemFile(
            Long userId,
            Long projectId,
            SystemFilePath systemFilePath
    ) {
        validateId(userId, "用户ID");
        validateId(projectId, "项目ID");
        if (systemFilePath == null) {
            throw new BizException(ErrorCode.PARAM_INVALID, "系统文件路径不能为空");
        }
        return new StorageLocation(
                StorageLocation.PROJECT_BUCKET,
                buildProjectPrefix(userId, projectId).objectKey()
                        + "system/"
                        + systemFilePath.fixedPath()
        );
    }

    public StorageLocation buildSystemFile(
            Long userId,
            Long projectId,
            SystemFilePath systemFilePath,
            String relativePath
    ) {
        validateId(userId, "用户ID");
        validateId(projectId, "项目ID");
        if (systemFilePath == null) {
            throw new BizException(ErrorCode.PARAM_INVALID, "系统文件路径不能为空");
        }
        return new StorageLocation(
                StorageLocation.PROJECT_BUCKET,
                buildProjectPrefix(userId, projectId).objectKey()
                        + "system/"
                        + systemFilePath.resolve(relativePath)
        );
    }

    public StorageLocation buildProjectPrefix(Long userId, Long projectId) {
        validateId(userId, "用户ID");
        validateId(projectId, "项目ID");
        return new StorageLocation(
                StorageLocation.PROJECT_BUCKET,
                "%s/%d/%d/".formatted(ROOT_PREFIX, userId, projectId)
        );
    }

    public String buildStorageName(String fileName, String storageUuid) {
        String normalizedFileName = normalizeFileName(fileName);
        String normalizedStorageUuid = normalizeStorageUuid(storageUuid);
        int dotIndex = normalizedFileName.lastIndexOf('.');
        //处理诸如：（处理诸如：（1）无扩展名 -> readme （2）隐藏文件 -> .gitignore （3）末尾为点 -> file.
        if (dotIndex <= 0 || dotIndex == normalizedFileName.length() - 1) {
            return normalizedFileName + "-" + normalizedStorageUuid;
        }
        // 获取文件名以及扩展格式名
        String baseName = normalizedFileName.substring(0, dotIndex);
        String extension = normalizedFileName.substring(dotIndex);
        return baseName + "-" + normalizedStorageUuid + extension;
    }

    public String relativeObjectPath(Long userId, Long projectId, String objectKey) {
        String prefix = buildProjectPrefix(userId, projectId).objectKey();
        if (objectKey == null || !objectKey.startsWith(prefix)) {
            throw new BizException(ErrorCode.PARAM_INVALID, "对象键不属于指定项目");
        }
        return objectKey.substring(prefix.length());
    }

    private String normalizeFileName(String fileName) {
        if (fileName == null) {
            throw invalidFileName();
        }
        String normalized = Normalizer.normalize(fileName, Normalizer.Form.NFC);
        boolean hasControlCharacter = normalized.codePoints().anyMatch(Character::isISOControl);
        if (normalized.isBlank()
                || ".".equals(normalized)
                || "..".equals(normalized)
                || normalized.contains("/")
                || normalized.contains("\\")
                || hasControlCharacter) {
            throw invalidFileName();
        }
        return normalized;
    }

    private String normalizeStorageUuid(String storageUuid) {
        if (storageUuid == null) {
            throw new BizException(ErrorCode.PARAM_INVALID, "文件存储标识不能为空");
        }
        String normalized = storageUuid.toLowerCase(Locale.ROOT);
        if (!normalized.matches(STORAGE_UUID_PATTERN)) {
            throw new BizException(ErrorCode.PARAM_INVALID, "文件存储标识必须是16位十六进制字符串");
        }
        return normalized;
    }

    private void validateId(Long id, String fieldName) {
        if (id == null || id <= 0) {
            throw new BizException(ErrorCode.PARAM_INVALID, fieldName + "必须大于0");
        }
    }

    private BizException invalidFileName() {
        return new BizException(ErrorCode.PARAM_INVALID, "文件名不合法");
    }
}
