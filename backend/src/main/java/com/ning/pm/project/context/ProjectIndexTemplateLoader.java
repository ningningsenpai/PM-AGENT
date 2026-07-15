package com.ning.pm.project.context;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.project.context.dto.ProjectIndex;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.InputStream;

/**
 * ProjectIndexTemplateLoader 每次从固定模板反序列化新的索引对象，避免修改共享模板状态。
 *
 * @author ning
 * @date 2026-07-15
 */
@Component
@RequiredArgsConstructor
public class ProjectIndexTemplateLoader {

    private static final String TEMPLATE_PATH = "templates/project-context/index-template.json";

    private final ObjectMapper objectMapper;

    // 返回
    public ProjectIndex load() {
        ClassPathResource resource = new ClassPathResource(TEMPLATE_PATH);
        try (InputStream inputStream = resource.getInputStream()) {
            return objectMapper.readValue(inputStream, ProjectIndex.class);
        } catch (IOException exception) {
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_INIT_FAILED,
                    "读取项目上下文索引模板失败",
                    exception
            );
        }
    }
}
