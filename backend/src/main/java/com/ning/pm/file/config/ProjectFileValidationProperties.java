package com.ning.pm.file.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;

import java.util.LinkedHashSet;
import java.util.Set;

/**
 * ProjectFileValidationProperties 保存项目文件类型校验规则。
 *
 * @author ning
 * @date 2026-07-13
 */
@Getter
@Setter
@ConfigurationProperties(prefix = "pm-agent.file.validation")
public class ProjectFileValidationProperties {

    private Set<String> ignoredDirectoryNames = new LinkedHashSet<>();
    private Set<String> ignoredFileNames = new LinkedHashSet<>();
    private Set<String> allowedExtensions = new LinkedHashSet<>();
    private Set<String> blockedExtensions = new LinkedHashSet<>();
    private Set<String> blockedMimeTypes = new LinkedHashSet<>();
}
