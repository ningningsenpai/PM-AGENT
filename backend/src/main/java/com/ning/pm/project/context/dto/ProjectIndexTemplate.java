package com.ning.pm.project.context.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

/**
 * ProjectIndexTemplate 保存项目上下文索引的版本化模板配置。
 *
 * @author ning
 * @date 2026-07-16
 */
@JsonIgnoreProperties(ignoreUnknown = true)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ProjectIndexTemplate(
        String schemaVersion
) {
}
