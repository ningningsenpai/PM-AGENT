package com.ning.pm.infrastructure.messaging.outbox;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileBatchStageCompletedEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * 在业务事务内保存待发布事件，使数据库状态和 RabbitMQ 消息具备最终一致性。
 */
@Service
@RequiredArgsConstructor
public class EventOutboxService {

    private final EventOutboxMapper outboxMapper;
    private final ObjectMapper objectMapper;

    public void enqueue(
            String exchange,
            String routingKey,
            FileBatchStageCompletedEvent event
    ) {
        EventOutbox outbox = new EventOutbox();
        outbox.setEventId(event.eventId());
        outbox.setEventType(FileBatchStageCompletedEvent.class.getName());
        outbox.setExchangeName(exchange);
        outbox.setRoutingKey(routingKey);
        outbox.setPayloadJson(serialize(event));
        outbox.setStatus(OutboxStatus.PENDING);
        outbox.setPublishAttempts(0);
        outbox.setNextRetryAt(LocalDateTime.now());
        outboxMapper.insert(outbox);
    }

    private String serialize(FileBatchStageCompletedEvent event) {
        try {
            return objectMapper.writeValueAsString(event);
        } catch (JsonProcessingException exception) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Outbox事件序列化失败", exception);
        }
    }
}
