package com.ning.pm.infrastructure.messaging.rabbitmq;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * RabbitMqConfigTest 验证RabbitMQ基础配置使用JSON消息转换器。
 *
 * @author ning
 * @date 2026-07-13
 */
class RabbitMqConfigTest {

    @Test
    void shouldCreateJacksonMessageConverter() {
        RabbitMqConfig config = new RabbitMqConfig();

        assertThat(config.rabbitMessageConverter(new ObjectMapper()))
                .isInstanceOf(Jackson2JsonMessageConverter.class);
    }
}
