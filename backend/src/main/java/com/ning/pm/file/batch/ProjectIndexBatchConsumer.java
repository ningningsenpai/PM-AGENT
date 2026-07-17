package com.ning.pm.file.batch;

import com.ning.pm.infrastructure.messaging.rabbitmq.FileMessageTopology;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileBatchStageCompletedEvent;
import com.ning.pm.project.context.ProjectIndexService;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.repository.ProjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

/**
 * 上传批次和解析批次共用同一索引投影消费者，始终从 MySQL 最新状态全量构建。
 */
@Component
@RequiredArgsConstructor
public class ProjectIndexBatchConsumer {

    private final ProjectMapper projectMapper;
    private final ProjectIndexService projectIndexService;

    @RabbitListener(queues = FileMessageTopology.PROJECT_INDEX_QUEUE)
    public void consume(FileBatchStageCompletedEvent event) {
        Project project = projectMapper.selectById(event.projectId());
        if (project != null) {
            projectIndexService.rebuild(project);
        }
    }
}
