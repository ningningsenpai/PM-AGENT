package com.ning.pm.infrastructure.storage;

import io.minio.MinioClient;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * MinioStorageConfig 创建MinIO客户端并绑定文件存储配置。
 *
 * @author ning
 * @date 2026-07-12
 */
@Configuration
@EnableConfigurationProperties(MinioProperties.class)
public class MinioStorageConfig {

    @Bean
    public MinioClient minioClient(MinioProperties properties) {
        return MinioClient.builder()
                .endpoint(properties.getEndpoint())
                .credentials(properties.getAccessKey(), properties.getSecretKey())
                .build();
    }
}
