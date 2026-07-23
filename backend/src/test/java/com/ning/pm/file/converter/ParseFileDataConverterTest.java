package com.ning.pm.file.converter;

import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.dto.parse.FileDetail;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/** ParseFileDataConverterTest 验证文件分析详情到数据库更新对象的字段映射。 */
class ParseFileDataConverterTest {

    private final ParseFileDataConverter converter = new ParseFileDataConverterImpl();

    @Test
    void toProjectFileUpdateShouldMapAnalysisFieldsOnly() {
        FileDetail detail = new FileDetail(
                "file-30",
                10L,
                30L,
                "1.0.0",
                "file-detail-v1",
                "2026-07-23T10:00:00",
                "2026-07-23T10:00:00",
                "a1b2c3d4e5f67890",
                "README-a1b2c3d4e5f67890.md",
                "system/file_details/README-a1b2c3d4e5f67890.json",
                "docs/README.md",
                "project/README-a1b2c3d4e5f67890.md",
                100L,
                "text/markdown",
                "content",
                "docs",
                "documentation",
                "doc",
                "markdown",
                "active",
                "medium",
                "项目说明",
                List.of("项目文件"),
                "说明项目结构",
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                List.of(),
                null
        );

        ProjectFile update = converter.toProjectFileUpdate(detail);

        assertThat(update.getDetailRef()).isEqualTo(detail.detailRef());
        assertThat(update.getAnalysisVersion()).isEqualTo("file-detail-v1");
        assertThat(update.getModule()).isEqualTo("docs");
        assertThat(update.getKeywords()).containsExactly("项目文件");
        assertThat(update.getId()).isNull();
        assertThat(update.getProjectId()).isNull();
    }
}
