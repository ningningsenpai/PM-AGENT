package com.ning.pm.infrastructure.messaging.rabbitmq;

import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.beans.factory.annotation.Qualifier;

/**
 * 文件异步链路 RabbitMQ 拓扑。业务消息使用版本化 routing key，失败消息进入独立死信队列。
 */
@Configuration(proxyBeanMethods = false)
public class FileMessageTopology {

    public static final String FILE_EXCHANGE = "pm-agent.project-file.events.v1";
    public static final String FILE_DETAIL_PARSE_QUEUE = "pm-agent.file-detail.parse.v1";
    public static final String FILE_DETAIL_PARSE_DLQ = "pm-agent.file-detail.parse.dlq.v1";
    public static final String PROJECT_INDEX_QUEUE = "pm-agent.project-index.project.v1";
    public static final String FILE_DETAIL_DISPATCH_QUEUE = "pm-agent.file-detail.dispatch.v1";
    public static final String PROJECT_INDEX_DLQ = "pm-agent.project-index.project.dlq.v1";
    public static final String FILE_DETAIL_DISPATCH_DLQ = "pm-agent.file-detail.dispatch.dlq.v1";
    public static final String FILE_DETAIL_REQUESTED_ROUTING_KEY = "project.file.detail.requested.v1";
    public static final String UPLOAD_BATCH_COMPLETED_ROUTING_KEY = "project.file.upload-batch.completed.v1";
    public static final String ANALYSIS_BATCH_COMPLETED_ROUTING_KEY = "project.file.analysis-batch.completed.v1";

    @Bean
    public TopicExchange fileExchange() {
        return new TopicExchange(FILE_EXCHANGE, true, false);
    }

    @Bean
    public Queue fileDetailParseDeadLetterQueue() {
        return QueueBuilder.durable(FILE_DETAIL_PARSE_DLQ).build();
    }

    @Bean
    public Queue fileDetailParseQueue() {
        return QueueBuilder.durable(FILE_DETAIL_PARSE_QUEUE)
                .deadLetterExchange("")
                .deadLetterRoutingKey(FILE_DETAIL_PARSE_DLQ)
                .build();
    }

    @Bean
    public Queue projectIndexQueue() {
        return QueueBuilder.durable(PROJECT_INDEX_QUEUE)
                .withArgument("x-single-active-consumer", true)
                .deadLetterExchange("")
                .deadLetterRoutingKey(PROJECT_INDEX_DLQ)
                .build();
    }

    @Bean
    public Queue fileDetailDispatchQueue() {
        return QueueBuilder.durable(FILE_DETAIL_DISPATCH_QUEUE)
                .deadLetterExchange("")
                .deadLetterRoutingKey(FILE_DETAIL_DISPATCH_DLQ)
                .build();
    }

    @Bean
    public Queue projectIndexDeadLetterQueue() {
        return QueueBuilder.durable(PROJECT_INDEX_DLQ).build();
    }

    @Bean
    public Queue fileDetailDispatchDeadLetterQueue() {
        return QueueBuilder.durable(FILE_DETAIL_DISPATCH_DLQ).build();
    }

    @Bean
    public Binding fileDetailParseBinding(
            @Qualifier("fileDetailParseQueue") Queue fileDetailParseQueue,
            TopicExchange fileExchange
    ) {
        return BindingBuilder.bind(fileDetailParseQueue)
                .to(fileExchange)
                .with(FILE_DETAIL_REQUESTED_ROUTING_KEY);
    }

    @Bean
    public Binding projectIndexUploadBinding(
            @Qualifier("projectIndexQueue") Queue projectIndexQueue,
            TopicExchange fileExchange
    ) {
        return BindingBuilder.bind(projectIndexQueue)
                .to(fileExchange)
                .with(UPLOAD_BATCH_COMPLETED_ROUTING_KEY);
    }

    @Bean
    public Binding projectIndexAnalysisBinding(
            @Qualifier("projectIndexQueue") Queue projectIndexQueue,
            TopicExchange fileExchange
    ) {
        return BindingBuilder.bind(projectIndexQueue)
                .to(fileExchange)
                .with(ANALYSIS_BATCH_COMPLETED_ROUTING_KEY);
    }

    @Bean
    public Binding fileDetailDispatchBinding(
            @Qualifier("fileDetailDispatchQueue") Queue fileDetailDispatchQueue,
            TopicExchange fileExchange
    ) {
        return BindingBuilder.bind(fileDetailDispatchQueue)
                .to(fileExchange)
                .with(UPLOAD_BATCH_COMPLETED_ROUTING_KEY);
    }
}
