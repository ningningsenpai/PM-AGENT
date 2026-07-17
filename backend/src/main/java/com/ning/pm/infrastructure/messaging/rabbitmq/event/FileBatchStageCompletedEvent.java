package com.ning.pm.infrastructure.messaging.rabbitmq.event;

import java.time.LocalDateTime;

/**
 * 上传或详情解析批次完成事件；同一信封供索引投影和详情分发消费者复用。
 */
public record FileBatchStageCompletedEvent(
        String eventId,
        Long batchId,
        Long projectId,
        String stage,
        String traceId,
        LocalDateTime occurredAt
) {
}
