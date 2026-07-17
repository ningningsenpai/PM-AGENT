package com.ning.pm.infrastructure.messaging.outbox;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

@Getter
@Setter
@TableName("pm_event_outbox")
public class EventOutbox extends BaseEntity {
    private String eventId;
    private String eventType;
    private String exchangeName;
    private String routingKey;
    private String payloadJson;
    private OutboxStatus status;
    private Integer publishAttempts;
    private LocalDateTime nextRetryAt;
    private LocalDateTime publishedAt;
    private String lastError;
}
