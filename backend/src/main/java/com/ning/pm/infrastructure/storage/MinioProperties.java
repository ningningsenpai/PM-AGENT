package com.ning.pm.infrastructure.storage;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * MinioProperties 保存文件模块所需的MinIO连接和限制配置。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@Setter
@ConfigurationProperties(prefix = "pm-agent.storage.minio")
public class MinioProperties {

    private String endpoint;
    private String accessKey;
    private String secretKey;
    private long maxFileSizeBytes = 50L * 1024 * 1024;
    private int readUrlExpirySeconds = 300;
    private int connectTimeoutSeconds = 2;
    private int readTimeoutSeconds = 10;
    private int writeTimeoutSeconds = 10;
}
