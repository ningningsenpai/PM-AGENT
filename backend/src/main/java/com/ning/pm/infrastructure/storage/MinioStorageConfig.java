package com.ning.pm.infrastructure.storage;

import io.minio.MinioClient;
import okhttp3.OkHttpClient;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.TimeUnit;

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
        OkHttpClient httpClient = new OkHttpClient.Builder()
                .connectTimeout(properties.getConnectTimeoutSeconds(), TimeUnit.SECONDS)
                .readTimeout(properties.getReadTimeoutSeconds(), TimeUnit.SECONDS)
                .writeTimeout(properties.getWriteTimeoutSeconds(), TimeUnit.SECONDS)
                .build();
        return MinioClient.builder()
                .endpoint(properties.getEndpoint())
                .credentials(properties.getAccessKey(), properties.getSecretKey())
                .httpClient(httpClient)
                .build();
    }
}
