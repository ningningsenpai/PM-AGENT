package com.ning.pm.migration;

import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.project.domain.Project;
import com.ning.pm.user.domain.User;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * FlywayMigrationContractTest 验证最新迁移会清理旧租户表，且当前持久化实体不再包含租户字段。
 *
 * @author ning
 * @date 2026-07-15
 */
class FlywayMigrationContractTest {

    @Test
    void latestMigrationShouldDropUnusedLegacyTablesInDependencyOrder() throws IOException {
        String sql = readMigration("V7__drop_legacy_tenant_tables.sql");

        int statusLogIndex = sql.indexOf("DROP TABLE IF EXISTS pm_task_status_log");
        int taskIndex = sql.indexOf("DROP TABLE IF EXISTS pm_task;");
        int memberIndex = sql.indexOf("DROP TABLE IF EXISTS pm_project_member");

        assertThat(statusLogIndex).isGreaterThanOrEqualTo(0);
        assertThat(taskIndex).isGreaterThan(statusLogIndex);
        assertThat(memberIndex).isGreaterThan(taskIndex);
    }

    @Test
    void currentPersistenceEntitiesShouldNotContainTenantField() {
        List<String> fieldNames = List.of(User.class, Project.class, ProjectFile.class).stream()
                .flatMap(type -> Arrays.stream(type.getDeclaredFields()))
                .map(Field::getName)
                .toList();

        assertThat(fieldNames).doesNotContain("tenantId", "deleted", "createdBy", "updatedBy");
    }

    private String readMigration(String fileName) throws IOException {
        ClassPathResource resource = new ClassPathResource("db/migration/" + fileName);
        return resource.getContentAsString(StandardCharsets.UTF_8);
    }
}
