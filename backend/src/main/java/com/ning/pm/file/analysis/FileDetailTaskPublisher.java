package com.ning.pm.file.analysis;

import com.ning.pm.common.trace.TraceContext;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.infrastructure.messaging.rabbitmq.event.FileParsingEvent;
import com.ning.pm.infrastructure.messaging.rabbitmq.publisher.FileEventPublisher;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.infrastructure.storage.StorageLocation;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * 为成功上传文件生成 Python 可消费的详情解析任务。
 */
@Component
@RequiredArgsConstructor
public class FileDetailTaskPublisher {

    private final AgentFileAnalysisProperties properties;
    private final ObjectStorageService objectStorageService;
    private final FileEventPublisher fileEventPublisher;

    public void publish(ProjectFile file) {
        publish(file, file.getDetailRef());
    }

    public void publish(ProjectFile file, String existingDetailRef) {
        String backendBaseUrl = properties.getBackendBaseUrl().replaceAll("/+$", "");
        String fileBaseUrl = backendBaseUrl + "/api/v1/agent/projects/"
                + file.getProjectId() + "/files/" + file.getId();
        FileParsingEvent event = new FileParsingEvent(
                UUID.randomUUID().toString(),
                file.getIngestBatchId(),
                file.getProjectId(),
                file.getId(),
                file.getStorageUuid(),
                file.getStorageName(),
                file.getRelativePath(),
                file.getMinioPath(),
                file.getSizeBytes(),
                file.getContentType(),
                "sha256:" + file.getContentHash(),
                objectStorageService.createReadUrl(new StorageLocation(
                        StorageLocation.PROJECT_BUCKET,
                        file.getObjectKey()
                )),
                fileBaseUrl + "/read-url",
                createExistingDetailUrl(file, existingDetailRef),
                file.getDetailRef(),
                properties.getAnalysisVersion(),
                fileBaseUrl + "/analysis-result",
                TraceContext.getTraceId(),
                LocalDateTime.now()
        );
        fileEventPublisher.publishParsing(event);
    }

    private String createExistingDetailUrl(ProjectFile file, String existingDetailRef) {
        if (file.getAnalyzedAt() == null || file.getMinioPath() == null
                || existingDetailRef == null
                || !file.getObjectKey().endsWith(file.getMinioPath())) {
            return null;
        }
        String projectPrefix = file.getObjectKey().substring(
                0,
                file.getObjectKey().length() - file.getMinioPath().length()
        );
        return objectStorageService.createReadUrl(new StorageLocation(
                StorageLocation.PROJECT_BUCKET,
                projectPrefix + existingDetailRef
        ));
    }
}
