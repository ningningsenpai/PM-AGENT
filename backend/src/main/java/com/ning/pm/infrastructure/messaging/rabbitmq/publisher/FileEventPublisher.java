package com.ning.pm.infrastructure.messaging.rabbitmq.publisher;

import com.ning.pm.infrastructure.messaging.rabbitmq.FileMessageTopology;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileParsingEvent;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.UUID;

@Component
@RequiredArgsConstructor
public class FileEventPublisher {

    private final RabbitTemplate rabbitTemplate;

    public void publishParsing(Long projectId, Long fileId, String traceId) {
        FileParsingEvent event = new FileParsingEvent(
                UUID.randomUUID().toString(),
                traceId,
                projectId,
                fileId,
                LocalDateTime.now()
        );

        rabbitTemplate.convertAndSend(
                FileMessageTopology.FILE_EXCHANGE,
                FileMessageTopology.FILE_PARSING_ROUTING_KEY,
                event
        );
    }
}