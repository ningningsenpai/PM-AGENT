package com.ning.pm.file.service;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.file.config.ProjectFileValidationProperties;
import lombok.RequiredArgsConstructor;
import org.apache.tika.Tika;
import org.springframework.stereotype.Component;

import java.util.Locale;
import java.util.Set;

/**
 * ProjectFileUploadValidator 校验项目文件扩展名并根据文件内容识别MIME类型。
 *
 * @author ning
 * @date 2026-07-13
 */
@Component
@RequiredArgsConstructor
public class ProjectFileUploadValidator {

    private final ProjectFileValidationProperties properties;
    private final Tika tika = new Tika();

    /** 校验相对路径中的忽略目录与固定文件名。 */
    public void validateRelativePath(String normalizedRelativePath) {
        String[] pathSegments = normalizedRelativePath.split("/");
        for (int index = 0; index < pathSegments.length - 1; index++) {
            String directoryName = pathSegments[index];
            if (containsIgnoreCase(properties.getIgnoredDirectoryNames(), directoryName)) {
                throw new BizException(
                        ErrorCode.FILE_PATH_IGNORED,
                        "文件路径命中忽略目录：" + directoryName
                );
            }
        }

        String fileName = pathSegments[pathSegments.length - 1];
        if (containsIgnoreCase(properties.getIgnoredFileNames(), fileName)) {
            throw new BizException(
                    ErrorCode.FILE_PATH_IGNORED,
                    "文件名命中忽略规则：" + fileName
            );
        }
    }

    /** 黑名单优先；白名单为空时不限制扩展名。 */
    public void validateExtension(String extension) {
        String normalizedExtension = normalizeExtension(extension);
        if (containsExtension(properties.getBlockedExtensions(), normalizedExtension)) {
            throw new BizException(
                    ErrorCode.FILE_EXTENSION_NOT_ALLOWED,
                    "禁止上传该扩展名的文件：" + displayExtension(normalizedExtension)
            );
        }
        Set<String> allowedExtensions = properties.getAllowedExtensions();
        if (allowedExtensions != null
                && !allowedExtensions.isEmpty()
                && !containsExtension(allowedExtensions, normalizedExtension)) {
            throw new BizException(
                    ErrorCode.FILE_EXTENSION_NOT_ALLOWED,
                    "文件扩展名不在白名单中：" + displayExtension(normalizedExtension)
            );
        }
    }

    /** 使用文件内容探测MIME，并拦截伪装扩展名的危险文件。 */
    public String detectAndValidateMimeType(byte[] content) {
        String detectedMimeType = tika.detect(content).toLowerCase(Locale.ROOT);
        if (containsIgnoreCase(properties.getBlockedMimeTypes(), detectedMimeType)) {
            throw new BizException(
                    ErrorCode.FILE_MIME_TYPE_BLOCKED,
                    "禁止上传该内容类型的文件：" + detectedMimeType
            );
        }
        return detectedMimeType;
    }

    private boolean containsExtension(Set<String> configuredExtensions, String extension) {
        if (configuredExtensions == null) {
            return false;
        }
        return configuredExtensions.stream()
                .map(this::normalizeExtension)
                .anyMatch(extension::equals);
    }

    private boolean containsIgnoreCase(Set<String> configuredValues, String value) {
        if (configuredValues == null || value == null) {
            return false;
        }
        String normalizedValue = value.trim().toLowerCase(Locale.ROOT);
        return configuredValues.stream()
                .filter(configuredValue -> configuredValue != null && !configuredValue.isBlank())
                .map(configuredValue -> configuredValue.trim().toLowerCase(Locale.ROOT))
                .anyMatch(normalizedValue::equals);
    }

    private String normalizeExtension(String extension) {
        if (extension == null || extension.isBlank()) {
            return "";
        }
        String normalized = extension.trim().toLowerCase(Locale.ROOT);
        return normalized.startsWith(".") ? normalized.substring(1) : normalized;
    }

    private String displayExtension(String extension) {
        return extension.isEmpty() ? "无扩展名" : "." + extension;
    }
}
