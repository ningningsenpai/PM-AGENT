package com.ning.pm.file.service.storage;

import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.StorageLocation;
import com.ning.pm.project.domain.Project;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** FileDetailStorageLocationResolverTest 验证文件详情路径只能落在受控目录。 */
class FileDetailStorageLocationResolverTest {

    private final FileDetailStorageLocationResolver resolver =
            new FileDetailStorageLocationResolver(new FileStorageLocationFactory());

    @Test
    void resolveShouldBuildProjectScopedLocation() {
        StorageLocation location = resolver.resolve(
                project(),
                "system/file_details/README-a1b2c3d4e5f67890.json"
        );

        assertThat(location.bucket()).isEqualTo("pm-agent");
        assertThat(location.objectKey()).isEqualTo(
                "PM-AGENT/1/10/system/file_details/README-a1b2c3d4e5f67890.json"
        );
    }

    @Test
    void resolveShouldRejectPathTraversal() {
        assertThatThrownBy(() -> resolver.resolve(
                project(),
                "system/file_details/../index.json"
        )).hasMessageContaining("路径不合法");
    }

    private Project project() {
        Project project = new Project();
        project.setId(10L);
        project.setOwnerUserId(1L);
        return project;
    }
}
