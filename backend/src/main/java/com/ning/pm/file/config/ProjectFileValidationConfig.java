package com.ning.pm.file.config;

import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * ProjectFileValidationConfig 绑定项目文件类型校验配置。
 *
 * @author ning
 * @date 2026-07-13
 */
@Configuration
@EnableConfigurationProperties(ProjectFileValidationProperties.class)
public class ProjectFileValidationConfig {
}
