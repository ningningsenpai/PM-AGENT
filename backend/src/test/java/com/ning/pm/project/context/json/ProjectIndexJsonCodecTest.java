package com.ning.pm.project.context.json;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ning.pm.project.context.dto.ProjectIndex;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/** ProjectIndexJsonCodecTest 验证项目索引的解析、补全和序列化。 */
class ProjectIndexJsonCodecTest {

    private final ProjectIndexJsonCodec codec = new ProjectIndexJsonCodec(new ObjectMapper());

    @Test
    void completeShouldReplaceFileEntriesAndSummary() {
        ObjectNode index = codec.deserialize("{\"summary\":{}}".getBytes(StandardCharsets.UTF_8));
        ProjectIndex.FileEntry entry = new ProjectIndex.FileEntry(
                30L,
                "a1b2c3d4e5f67890",
                "docs/README.md",
                "README.md",
                "README-a1b2c3d4e5f67890.md",
                "project/README-a1b2c3d4e5f67890.md",
                100L,
                "text/markdown",
                "active",
                "qf:sha256:quick",
                "sha256:content",
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                null,
                List.of()
        );

        codec.complete(index, List.of(entry), List.of(), 2L, 1L);
        String json = new String(codec.serialize(index), StandardCharsets.UTF_8);

        assertThat(index.get("project")).hasSize(1);
        assertThat(index.path("summary").path("total_nodes").asLong()).isEqualTo(2L);
        assertThat(index.path("summary").path("active_files").asLong()).isEqualTo(1L);
        assertThat(index.path("summary").path("fail_nodes").asLong()).isEqualTo(1L);
        assertThat(json).doesNotContain("\r");
    }
}
