package com.ning.pm.infrastructure.messaging.rabbitmq;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * RabbitMqConfig 提供RabbitMQ基础序列化配置，不声明业务交换机、队列或监听器。
 *
 * @author ning
 * @date 2026-07-13
 */
@Configuration(proxyBeanMethods = false)
public class RabbitMqConfig {

    @Bean
    public Jackson2JsonMessageConverter rabbitMessageConverter(ObjectMapper objectMapper) {
        return new Jackson2JsonMessageConverter(objectMapper);
    }
}
