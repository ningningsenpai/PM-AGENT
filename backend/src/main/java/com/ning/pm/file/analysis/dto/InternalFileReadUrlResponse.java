package com.ning.pm.file.analysis.dto;

import java.time.LocalDateTime;

public record InternalFileReadUrlResponse(
        String sourceUrl,
        LocalDateTime expiresAt
) {
}
