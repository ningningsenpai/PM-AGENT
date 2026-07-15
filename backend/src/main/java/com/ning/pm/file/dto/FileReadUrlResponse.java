package com.ning.pm.file.dto;

import java.time.LocalDateTime;

/**
 * FileReadUrlResponse 返回短期有效的文件只读地址。
 *
 * @author ning
 * @date 2026-07-12
 */
public record FileReadUrlResponse(
        Long fileId,
        String fileName,
        String url,
        LocalDateTime expiresAt
) {
}
