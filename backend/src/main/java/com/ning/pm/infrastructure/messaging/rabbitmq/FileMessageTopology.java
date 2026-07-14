package com.ning.pm.infrastructure.messaging.rabbitmq;

import org.springframework.amqp.core.*;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class FileMessageTopology {

    public static final String FILE_EXCHANGE = "pm-agent.file.events";
    public static final String FILE_PARSING_QUEUE = "pm-agent.file.parsing";
    public static final String FILE_PARSING_ROUTING_KEY = "file.parsing";

    @Bean
    public DirectExchange fileExchange() {
        return new DirectExchange(FILE_EXCHANGE, true, false);
    }

    @Bean
    public Queue fileParsingQueue() {
        return QueueBuilder.durable(FILE_PARSING_QUEUE).build();
    }

    @Bean
    public Binding fileParsingBinding(
            Queue fileUploadedQueue,
            DirectExchange fileExchange
    ) {
        return BindingBuilder.bind(fileUploadedQueue)
                .to(fileExchange)
                .with(FILE_PARSING_ROUTING_KEY);
    }
}