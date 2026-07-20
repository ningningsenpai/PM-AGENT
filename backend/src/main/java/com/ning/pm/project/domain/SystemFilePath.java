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

    INDEX("index.json", false),
    PROJECT_SPECIFICATION("project_specification.json", false),
    LONG_TERM_MEMORY("long_term_memory.json", false),
    SHORT_TERM_MEMORY("short_term_memory.json", false),
    USER_HABITS("user_habits", true),
    UPDATE_JOURNAL("update_journal.jsonl", false);

    private static final int MAX_RELATIVE_PATH_LENGTH = 512;

    private final String path;
    private final boolean directory;

    SystemFilePath(String path, boolean directory) {
        this.path = path;
        this.directory = directory;
    }

    public String fixedPath() {
        if (directory) {
            throw new BizException(ErrorCode.PARAM_INVALID, "系统目录必须指定相对路径");
        }
        return path;
    }

    public String directoryPath() {
        return path + "/";
    }

    /** 仅允许在预定义系统目录下拼接受校验的相对路径。 */
    public String resolve(String relativePath) {
        if (!directory) {
            throw new BizException(ErrorCode.PARAM_INVALID, "固定系统文件不接受相对路径");
        }
        return path + "/" + normalizeRelativePath(relativePath);
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

    private BizException invalidRelativePath() {
        return new BizException(ErrorCode.PARAM_INVALID, "系统文件路径必须是合法相对路径");
    }
}
