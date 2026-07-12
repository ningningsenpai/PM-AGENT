package com.ning.pm.file.service;

import cn.hutool.crypto.digest.DigestUtil;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/**
 * FileFingerprintService 负责路径规范化、快速指纹和内容哈希计算。
 *
 * @author ning
 * @date 2026-07-12
 */
@Component
public class FileFingerprintService {

    private static final int MAX_PATH_LENGTH = 512;

    /**
     * 规范化项目内相对路径，拒绝绝对路径和目录穿越片段。
     */
    public String normalizeRelativePath(String relativePath) {
        if (relativePath == null) {
            throw new BizException(ErrorCode.PARAM_INVALID, "文件相对路径不能为空");
        }
        String normalized = relativePath.trim().replace('\\', '/');
        while (normalized.startsWith("./")) {
            normalized = normalized.substring(2);
        }
        if (normalized.startsWith("/") || normalized.matches("^[A-Za-z]:/.*")) {
            throw new BizException(ErrorCode.PARAM_INVALID, "文件路径必须是项目内相对路径");
        }
        boolean illegalSegment = Arrays.stream(normalized.split("/"))
                .anyMatch(segment -> segment.isBlank() || ".".equals(segment) || "..".equals(segment));
        if (normalized.isBlank() || normalized.length() > MAX_PATH_LENGTH || illegalSegment) {
            throw new BizException(ErrorCode.PARAM_INVALID, "文件相对路径不合法");
        }
        return normalized;
    }

    public String pathHash(String normalizedRelativePath) {
        return DigestUtil.sha256Hex(normalizedRelativePath);
    }

    public String quickFingerprint(String normalizedRelativePath, long sizeBytes, long sourceMtimeMs) {
        String raw = normalizedRelativePath + '\0' + sizeBytes + '\0' + sourceMtimeMs;
        return DigestUtil.sha256Hex(raw.getBytes(StandardCharsets.UTF_8));
    }

    public String contentHash(byte[] content) {
        return DigestUtil.sha256Hex(content);
    }

    public String fileName(String normalizedRelativePath) {
        int separatorIndex = normalizedRelativePath.lastIndexOf('/');
        return separatorIndex < 0 ? normalizedRelativePath : normalizedRelativePath.substring(separatorIndex + 1);
    }

    public String extension(String fileName) {
        int dotIndex = fileName.lastIndexOf('.');
        if (dotIndex <= 0 || dotIndex == fileName.length() - 1) {
            return null;
        }
        return fileName.substring(dotIndex + 1).toLowerCase();
    }
}
