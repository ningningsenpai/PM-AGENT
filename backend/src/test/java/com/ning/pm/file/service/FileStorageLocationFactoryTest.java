package com.ning.pm.file.service;

import com.ning.pm.common.exception.BizException;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.domain.SystemFilePath;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * FileStorageLocationFactoryTest 验证固定桶、稳定文件名和受控系统路径。
 *
 * @author ning
 * @date 2026-07-15
 */
class FileStorageLocationFactoryTest {

    private final FileStorageLocationFactory factory = new FileStorageLocationFactory();

    @Test
    void projectFileShouldUseStableStorageUuid() {
        StorageLocation location = factory.buildProjectFile(
                1L,
                10L,
                "README.md",
                "a1b2c3d4e5f67890"
        );

        assertThat(location.bucket()).isEqualTo("pm-agent");
        assertThat(location.objectKey()).isEqualTo(
                "PM-AGENT/1/10/project/README-a1b2c3d4e5f67890.md"
        );
        assertThat(location.fullPath()).startsWith("pm-agent/PM-AGENT/");
    }

    @Test
    void systemIndexShouldUseFixedPath() {
        StorageLocation location = factory.buildSystemFile(1L, 10L, SystemFilePath.INDEX);

        assertThat(location.objectKey()).isEqualTo("PM-AGENT/1/10/system/index.json");
    }

    @Test
    void publicRegularFileFactoryShouldRejectSystemBusiness() {
        assertThatThrownBy(() -> factory.buildRegularFile(
                1L,
                10L,
                FileBusinessType.SYSTEM,
                "index.json",
                "a1b2c3d4e5f67890"
        )).isInstanceOf(BizException.class)
                .hasMessageContaining("系统文件");
    }

    @Test
    void traversalLikeFileNameShouldBeRejected() {
        assertThatThrownBy(() -> factory.buildProjectFile(
                1L,
                10L,
                "../README.md",
                "a1b2c3d4e5f67890"
        )).isInstanceOf(BizException.class)
                .hasMessage("文件名不合法");
    }
}
