package com.ning.pm.project.context.json;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.project.context.dto.LongTermMemory;
import com.ning.pm.project.context.dto.ProjectSpecification;
import com.ning.pm.project.context.dto.ShortTermMemory;
import com.ning.pm.project.context.dto.UpdateJournalEvent;
import com.ning.pm.project.context.dto.UserHabits;
import org.junit.jupiter.api.Test;

import java.nio.charset.StandardCharsets;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** ProjectContextJsonSerializerTest 验证剩余项目上下文对象的字段结构和序列化格式。 */
class ProjectContextJsonSerializerTest {

    private static final String UPDATED_AT = "2026-07-24T10:00:00";

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ProjectContextJsonSerializer serializer =
            new ProjectContextJsonSerializer(objectMapper);

    @Test
    void emptyDocumentsShouldContainCompleteRootStructure() throws Exception {
        JsonNode specification = read(serializer.serialize(
                ProjectSpecification.empty(10L, UPDATED_AT)
        ));
        JsonNode longTermMemory = read(serializer.serialize(
                LongTermMemory.empty(10L, UPDATED_AT)
        ));
        JsonNode shortTermMemory = read(serializer.serialize(
                ShortTermMemory.empty(10L, UPDATED_AT)
        ));
        JsonNode userHabits = read(serializer.serialize(
                UserHabits.empty(10L, UserHabits.CATEGORY_WORK, UPDATED_AT)
        ));

        assertThat(specification.path("schema_version").asText()).isEqualTo("1.0.0");
        assertThat(specification.path("project_specification").path("development_stage").isObject())
                .isTrue();
        assertThat(specification.path("project_specification").path("technical_constraints").isArray())
                .isTrue();
        assertThat(longTermMemory.path("long_term_memory").isArray()).isTrue();
        assertThat(shortTermMemory.path("short_term_memory").isArray()).isTrue();
        assertThat(shortTermMemory.path("promotion_candidates").isArray()).isTrue();
        assertThat(userHabits.path("category").asText()).isEqualTo("work");
        assertThat(userHabits.path("user_habits").isArray()).isTrue();
        assertThat(userHabits.path("ignored_items").isArray()).isTrue();
    }

    @Test
    void nestedFieldsShouldUseSnakeCase() throws Exception {
        ShortTermMemory memory = new ShortTermMemory(
                10L,
                ShortTermMemory.SCHEMA_VERSION,
                UPDATED_AT,
                List.of(new ShortTermMemory.Memory(
                        "task-json-fields",
                        "task",
                        "补全 JSON 字段",
                        "正在补全项目上下文 JSON 字段。",
                        "backend",
                        "active",
                        "high",
                        "high",
                        "本轮实现完成后复查",
                        "运行后端测试",
                        true,
                        List.of("项目上下文"),
                        List.of(new ShortTermMemory.SourceRef("conversation", "用户要求补全字段")),
                        List.of(new ShortTermMemory.RelatedFile(
                                "backend/src/main/java/com/ning/pm/project/context/json",
                                "implementation_reference"
                        )),
                        List.of(new ShortTermMemory.Evidence("recent_conversation", "补全剩余 JSON 字段")),
                        UPDATED_AT,
                        UPDATED_AT
                )),
                List.of(new ShortTermMemory.PromotionCandidate(
                        "task-json-fields",
                        "project_specification",
                        "完成后可沉淀为格式规范",
                        "pending_review"
                )),
                List.of(new ShortTermMemory.Change(
                        "chg-json-fields",
                        "created",
                        "task-json-fields",
                        "创建短期记忆",
                        UPDATED_AT
                )),
                List.of()
        );

        JsonNode json = read(serializer.serialize(memory));

        assertThat(json.path("short_term_memory").get(0).path("ttl_hint").asText())
                .isEqualTo("本轮实现完成后复查");
        assertThat(json.path("short_term_memory").get(0).path("promote_candidate").asBoolean())
                .isTrue();
        assertThat(json.path("promotion_candidates").get(0).path("source_memory_id").asText())
                .isEqualTo("task-json-fields");
        assertThat(json.path("changes").get(0).path("change_id").asText())
                .isEqualTo("chg-json-fields");
    }

    @Test
    void journalShouldUseOneJsonObjectPerLine() {
        List<UpdateJournalEvent> events = List.of(
                new UpdateJournalEvent(
                        "evt-001",
                        10L,
                        "project_specification_updated",
                        "system/project_specification.json",
                        "AGENTS.md",
                        "已更新项目规范。",
                        UPDATED_AT
                ),
                new UpdateJournalEvent(
                        "evt-002",
                        10L,
                        "user_habit_updated",
                        "system/user_habits/work.json",
                        "conversation:100",
                        "已更新工作习惯。",
                        UPDATED_AT
                )
        );

        String jsonl = new String(serializer.serializeJournal(events), StandardCharsets.UTF_8);

        assertThat(jsonl.lines()).hasSize(2);
        assertThat(jsonl).contains("\"event_id\":\"evt-001\"");
        assertThat(jsonl).contains("\"project_id\":10");
        assertThat(jsonl).endsWith("\n");
    }

    @Test
    void emptyJournalShouldProduceEmptyContent() {
        assertThat(serializer.serializeJournal(List.of())).isEmpty();
    }

    @Test
    void invalidHabitCategoryShouldBeRejected() {
        assertThatThrownBy(() -> UserHabits.empty(10L, "other", UPDATED_AT))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("用户习惯分类不合法");
    }

    private JsonNode read(byte[] content) throws Exception {
        return objectMapper.readTree(content);
    }
}
