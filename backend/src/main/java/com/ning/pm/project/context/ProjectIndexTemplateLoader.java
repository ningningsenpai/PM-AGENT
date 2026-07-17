package com.ning.pm.project.context;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.project.context.dto.ProjectIndexTemplate;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;

/**
 * ProjectIndexTemplateLoader 读取项目上下文索引的版本化模板配置。
 *
 * @author ning
 * @date 2026-07-15
 */
@Component
@RequiredArgsConstructor
public class ProjectIndexTemplateLoader {

    private static final String TEMPLATE_PATH = "templates/project-context/index-template.json";

    private final ObjectMapper objectMapper;

    /** 读取并校验索引格式版本配置。 */
    public ProjectIndexTemplate load() {
        ClassPathResource resource = new ClassPathResource(TEMPLATE_PATH);
        try (InputStream inputStream = resource.getInputStream()) {
            ProjectIndexTemplate template = objectMapper.readValue(inputStream, ProjectIndexTemplate.class);
            if (template.schemaVersion() == null || template.schemaVersion().isBlank()) {
                throw new SystemException(
                        ErrorCode.PROJECT_INDEX_INIT_FAILED,
                        "项目上下文索引模板缺少schema_version"
                );
            }
            return template;
        } catch (IOException exception) {
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_INIT_FAILED,
                    "读取项目上下文索引模板失败",
                    exception
            );
        }
    }
}
