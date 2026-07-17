package com.ning.pm.project.context;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.ning.pm.file.service.FileStorageLocationFactory;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.project.context.dto.ProjectIndex;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

/**
 * ProjectIndexWriterTest 验证项目索引按固定缩进和换行格式写入对象存储。
 *
 * @author ning
 * @date 2026-07-15
 */
class ProjectIndexWriterTest {

    private final ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule());
    private final ObjectStorageService objectStorageService = mock(ObjectStorageService.class);
    private final ProjectIndexWriter writer = new ProjectIndexWriter(
            objectMapper,
            objectStorageService,
            new FileStorageLocationFactory()
    );

    @Test
    void writeIndexShouldUseFixedReadableJsonFormat() throws Exception {
        writer.writeIndex(1L, 10L, index());

        ArgumentCaptor<byte[]> contentCaptor = ArgumentCaptor.forClass(byte[].class);
        verify(objectStorageService).putObject(
                eq(writer.indexLocation(1L, 10L)),
                contentCaptor.capture(),
                eq("application/json")
        );
        String json = new String(contentCaptor.getValue(), StandardCharsets.UTF_8);

        assertThat(json)
                .startsWith("{\n")
                .contains("\n  \"project_id\" : 10,")
                .contains("\n  \"storage\" : {\n    \"provider\" : \"minio\",")
                .endsWith("\n}")
                .doesNotContain("\r");
        assertThat(objectMapper.readTree(json).get("project_name").asText()).isEqualTo("PM-Agent");
    }

    private ProjectIndex index() {
        LocalDateTime now = LocalDateTime.of(2026, 7, 15, 10, 0);
        return new ProjectIndex(
                10L,
                "PM-Agent",
                1L,
                "1.0.0",
                now,
                now,
                new ProjectIndex.Storage(
                        "minio",
                        "pm-agent",
                        "PM-AGENT/1/10/",
                        "system/index.json"
                ),
                new ProjectIndex.Summary(0, 0, 0),
                List.of(),
                List.of(),
                List.of(),
                new ProjectIndex.SystemSection(
                        "system/index.json",
                        "system/file_details/",
                        "system/project_specification.json",
                        "system/long_term_memory.json",
                        "system/short_term_memory.json",
                        "system/user_habits/",
                        "system/update_journal.jsonl"
                )
        );
    }
}
