package com.ning.pm.infrastructure.messaging.rabbitmq.event;

import java.time.LocalDateTime;

/**
 * Java 向 Python 发布的单文件详情解析任务，只携带稳定元数据和短期只读地址。
 */
public record FileParsingEvent(
        String eventId,
        Long batchId,
        Long projectId,
        Long fileId,
        String storageUuid,
        String storageName,
        String logicalPath,
        String minioPath,
        Long sizeBytes,
        String contentType,
        String contentHash,
        String sourceUrl,
        String readUrlRefreshUrl,
        String existingDetailUrl,
        String detailRef,
        String analysisVersion,
        String callbackUrl,
        String traceId,
        LocalDateTime occurredAt
) {
}
