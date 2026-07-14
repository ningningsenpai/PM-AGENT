package com.ning.pm.project.domain;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;

import java.util.Arrays;

/**
 * SystemFilePath 定义项目上下文系统文件的固定对象目录，并负责安全拼接对象键。
 *
 * @author ning
 * @date 2026-07-15
 */
public enum SystemFilePath {

    FILE_DETAILS("file_details"),
    USER_HABITS("user_habits");

    private static final int MAX_RELATIVE_PATH_LENGTH = 512;

    private final String directory;

    SystemFilePath(String directory) {
        this.directory = directory;
    }

    /**
     * 按项目、用户和系统目录生成完整对象键，并校验传入的相对路径。
     *
     * @param projectId 项目 ID
     * @param ownerUserId 项目所属用户 ID
     * @param relativePath 系统目录内的相对路径
     * @return 可用于对象存储的完整对象键
     */
    public String build(Long projectId, Long ownerUserId, String relativePath) {
        validateId(projectId, "项目ID");
        validateId(ownerUserId, "用户ID");
        String normalizedPath = normalizeRelativePath(relativePath);
        return "PM-AGENT/%d/%d/project/context/%s/%s".formatted(
                ownerUserId,
                projectId,
                directory,
                normalizedPath
        );
    }

    private String normalizeRelativePath(String relativePath) {
        if (relativePath == null) {
            throw invalidRelativePath();
        }
        String normalized = relativePath.trim().replace('\\', '/');
        while (normalized.startsWith("./")) {
            normalized = normalized.substring(2);
        }
        boolean absolutePath = normalized.startsWith("/") || normalized.matches("^[A-Za-z]:/.*");
        boolean illegalSegment = Arrays.stream(normalized.split("/", -1))
                .anyMatch(segment -> segment.isBlank() || ".".equals(segment) || "..".equals(segment));
        if (normalized.isBlank()
                || normalized.length() > MAX_RELATIVE_PATH_LENGTH
                || absolutePath
                || illegalSegment) {
            throw invalidRelativePath();
        }
        return normalized;
    }

    private void validateId(Long id, String fieldName) {
        if (id == null || id <= 0) {
            throw new BizException(ErrorCode.PARAM_INVALID, fieldName + "必须大于0");
        }
    }

    private BizException invalidRelativePath() {
        return new BizException(ErrorCode.PARAM_INVALID, "系统文件路径必须是合法相对路径");
    }
}
