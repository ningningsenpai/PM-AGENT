package com.ning.pm.infrastructure.messaging.outbox;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileBatchStageCompletedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 轮询发布 Outbox，收到 Broker confirm 后才标记成功；失败按上限十分钟退避。
 */
@Component
@Slf4j
@RequiredArgsConstructor
public class EventOutboxPublisher {

    private final EventOutboxMapper outboxMapper;
    private final ObjectMapper objectMapper;
    private final RabbitTemplate rabbitTemplate;

    @Scheduled(fixedDelayString = "${pm-agent.messaging.outbox-poll-interval-ms:1000}")
    public void publishPending() {
        List<EventOutbox> events = outboxMapper.selectList(new LambdaQueryWrapper<EventOutbox>()
                .eq(EventOutbox::getStatus, OutboxStatus.PENDING)
                .le(EventOutbox::getNextRetryAt, LocalDateTime.now())
                .orderByAsc(EventOutbox::getId)
                .last("LIMIT 100"));
        events.forEach(this::publishOne);
    }

    private void publishOne(EventOutbox outbox) {
        int claimed = outboxMapper.update(null, new LambdaUpdateWrapper<EventOutbox>()
                .eq(EventOutbox::getId, outbox.getId())
                .eq(EventOutbox::getStatus, OutboxStatus.PENDING)
                .le(EventOutbox::getNextRetryAt, LocalDateTime.now())
                .set(EventOutbox::getNextRetryAt, LocalDateTime.now().plusSeconds(30)));
        if (claimed == 0) {
            return;
        }
        try {
            FileBatchStageCompletedEvent event = objectMapper.readValue(
                    outbox.getPayloadJson(),
                    FileBatchStageCompletedEvent.class
            );
            CorrelationData correlationData = new CorrelationData(outbox.getEventId());
            rabbitTemplate.convertAndSend(
                    outbox.getExchangeName(),
                    outbox.getRoutingKey(),
                    event,
                    correlationData
            );
            CorrelationData.Confirm confirm = correlationData.getFuture().get(5, TimeUnit.SECONDS);
            if (!confirm.isAck()) {
                throw new IllegalStateException("RabbitMQ未确认消息：" + confirm.getReason());
            }
            outboxMapper.update(null, new LambdaUpdateWrapper<EventOutbox>()
                    .eq(EventOutbox::getId, outbox.getId())
                    .eq(EventOutbox::getStatus, OutboxStatus.PENDING)
                    .set(EventOutbox::getStatus, OutboxStatus.PUBLISHED)
                    .set(EventOutbox::getPublishedAt, LocalDateTime.now())
                    .set(EventOutbox::getLastError, null)
                    .setSql("publish_attempts = publish_attempts + 1"));
        } catch (Exception exception) {
            int attempts = outbox.getPublishAttempts() == null ? 1 : outbox.getPublishAttempts() + 1;
            long delaySeconds = Math.min(600L, 1L << Math.min(attempts, 9));
            String message = exception.getMessage() == null ? "RabbitMQ事件发布失败" : exception.getMessage();
            outboxMapper.update(null, new LambdaUpdateWrapper<EventOutbox>()
                    .eq(EventOutbox::getId, outbox.getId())
                    .eq(EventOutbox::getStatus, OutboxStatus.PENDING)
                    .set(EventOutbox::getPublishAttempts, attempts)
                    .set(EventOutbox::getNextRetryAt, LocalDateTime.now().plusSeconds(delaySeconds))
                    .set(EventOutbox::getLastError, message.substring(0, Math.min(message.length(), 500))));
            log.warn("Outbox事件发布失败，等待重试 eventId={} attempts={}", outbox.getEventId(), attempts, exception);
        }
    }
}
