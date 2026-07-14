package com.ning.pm.file.service;

import com.ning.pm.common.exception.BizException;
import com.ning.pm.file.config.ProjectFileValidationProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * ProjectFileUploadValidatorTest 验证路径、扩展名和基于内容的MIME识别规则。
 *
 * @author ning
 * @date 2026-07-13
 */
class ProjectFileUploadValidatorTest {

    private ProjectFileValidationProperties properties;
    private ProjectFileUploadValidator validator;

    @BeforeEach
    void setUp() {
        properties = new ProjectFileValidationProperties();
        validator = new ProjectFileUploadValidator(properties);
    }

    @Test
    void ignoredDirectoryShouldMatchExactPathSegmentAndIgnoreCase() {
        properties.setIgnoredDirectoryNames(Set.of(".idea", "target", "test", "module", "node_modules"));

        assertThatThrownBy(() -> validator.validateRelativePath("demo/.IDEA/workspace.xml"))
                .isInstanceOf(BizException.class)
                .hasMessage("文件路径命中忽略目录：.IDEA");
        assertThatThrownBy(() -> validator.validateRelativePath("backend/target/classes/App.class"))
                .isInstanceOf(BizException.class);
        assertThatThrownBy(() -> validator.validateRelativePath("frontend/node_modules/pkg/index.js"))
                .isInstanceOf(BizException.class);
        assertThatThrownBy(() -> validator.validateRelativePath("src/test/java/AppTest.java"))
                .isInstanceOf(BizException.class);
        assertThatThrownBy(() -> validator.validateRelativePath("module/config.yml"))
                .isInstanceOf(BizException.class);
    }

    @Test
    void directoryRuleShouldNotRejectPartialNameMatch() {
        properties.setIgnoredDirectoryNames(Set.of("test", "module"));

        assertThatCode(() -> validator.validateRelativePath("src/contest/App.java"))
                .doesNotThrowAnyException();
        assertThatCode(() -> validator.validateRelativePath("src/modules/project/index.ts"))
                .doesNotThrowAnyException();
    }

    @Test
    void ignoredFileNameShouldMatchExactlyAndIgnoreCase() {
        properties.setIgnoredFileNames(Set.of(".DS_Store", ".env"));

        assertThatThrownBy(() -> validator.validateRelativePath("assets/.ds_store"))
                .isInstanceOf(BizException.class)
                .hasMessage("文件名命中忽略规则：.ds_store");
        assertThatThrownBy(() -> validator.validateRelativePath(".env"))
                .isInstanceOf(BizException.class);
        assertThatCode(() -> validator.validateRelativePath("docs/.env.example"))
                .doesNotThrowAnyException();
    }

    @Test
    void blockedExtensionShouldTakePrecedenceAndIgnoreCase() {
        properties.setAllowedExtensions(Set.of("exe", "java"));
        properties.setBlockedExtensions(Set.of(".EXE"));

        assertThatThrownBy(() -> validator.validateExtension("Exe"))
                .isInstanceOf(BizException.class)
                .hasMessage("禁止上传该扩展名的文件：.exe");
    }

    @Test
    void whitelistShouldBeDisabledWhenEmptyAndEnforcedWhenConfigured() {
        assertThatCode(() -> validator.validateExtension("txt"))
                .doesNotThrowAnyException();

        properties.setAllowedExtensions(Set.of("java", "md"));

        assertThatCode(() -> validator.validateExtension("JAVA"))
                .doesNotThrowAnyException();
        assertThatThrownBy(() -> validator.validateExtension("txt"))
                .isInstanceOf(BizException.class)
                .hasMessage("文件扩展名不在白名单中：.txt");
    }

    @Test
    void mimeTypeShouldComeFromFileContent() {
        byte[] pngContent = new byte[]{
                (byte) 0x89, 0x50, 0x4E, 0x47,
                0x0D, 0x0A, 0x1A, 0x0A
        };

        assertThat(validator.detectAndValidateMimeType(pngContent))
                .isEqualTo("image/png");
    }

    @Test
    void blockedMimeTypeShouldRejectExecutableWithDisguisedExtension() {
        properties.setBlockedMimeTypes(Set.of(
                "application/x-msdownload",
                "application/x-dosexec",
                "application/x-executable"
        ));
        byte[] executableContent = new byte[64];
        executableContent[0] = 'M';
        executableContent[1] = 'Z';

        assertThatThrownBy(() -> validator.detectAndValidateMimeType(executableContent))
                .isInstanceOf(BizException.class)
                .hasMessageStartingWith("禁止上传该内容类型的文件：");
    }
}
