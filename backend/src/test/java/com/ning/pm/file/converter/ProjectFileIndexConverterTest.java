package com.ning.pm.file.converter;

import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.enums.ProjectFileStatus;
import com.ning.pm.project.context.dto.ProjectIndex;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

/** ProjectFileIndexConverterTest 验证索引条目的字段映射和哈希格式。 */
class ProjectFileIndexConverterTest {

    private final ProjectFileIndexConverter converter = new ProjectFileIndexConverterImpl();

    @Test
    void toIndexEntryShouldMapAndNormalizeFields() {
        ProjectFile file = new ProjectFile();
        file.setId(30L);
        file.setStorageUuid("a1b2c3d4e5f67890");
        file.setRelativePath("docs/README.md");
        file.setFileName("README.md");
        file.setSizeBytes(100L);
        file.setContentType("text/markdown");
        file.setStatus(ProjectFileStatus.ACTIVE);
        file.setQuickFingerprint("quick");
        file.setContentHash("content");

        ProjectIndex.FileEntry entry = converter.toIndexEntry(
                file,
                "README-a1b2c3d4e5f67890.md",
                "project/README-a1b2c3d4e5f67890.md"
        );

        assertThat(entry.logicalPath()).isEqualTo("docs/README.md");
        assertThat(entry.status()).isEqualTo("active");
        assertThat(entry.quickFingerprint()).isEqualTo("qf:sha256:quick");
        assertThat(entry.contentHash()).isEqualTo("sha256:content");
        assertThat(entry.keywords()).isEmpty();
    }
}
