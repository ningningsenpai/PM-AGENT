package com.ning.pm.infrastructure.messaging.rabbitmq.publisher;

import com.ning.pm.infrastructure.messaging.rabbitmq.FileMessageTopology;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileParsingEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.stereotype.Component;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;

import java.util.concurrent.TimeUnit;

@Component
@RequiredArgsConstructor
public class FileEventPublisher {

    private final RabbitTemplate rabbitTemplate;

    public void publishParsing(FileParsingEvent event) {
        try {
            CorrelationData correlationData = new CorrelationData(event.eventId());
            rabbitTemplate.convertAndSend(
                    FileMessageTopology.FILE_EXCHANGE,
                    FileMessageTopology.FILE_DETAIL_REQUESTED_ROUTING_KEY,
                    event,
                    correlationData
            );
            CorrelationData.Confirm confirm = correlationData.getFuture().get(5, TimeUnit.SECONDS);
            if (!confirm.isAck()) {
                throw new IllegalStateException("RabbitMQ未确认详情解析任务：" + confirm.getReason());
            }
        } catch (Exception exception) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "文件详情解析任务发布失败", exception);
        }
    }
}
