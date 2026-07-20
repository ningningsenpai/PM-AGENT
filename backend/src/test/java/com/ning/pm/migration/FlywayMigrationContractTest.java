package com.ning.pm.migration;

import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.project.domain.Project;
import com.ning.pm.user.domain.User;
import org.junit.jupiter.api.Test;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * FlywayMigrationContractTest 验证唯一 V1 脚本直接创建当前持久化结构。
 *
 * @author ning
 * @date 2026-07-15
 */
class FlywayMigrationContractTest {

    @Test
    void migrationDirectoryShouldOnlyContainV1() throws IOException {
        Resource[] resources = new PathMatchingResourcePatternResolver()
                .getResources("classpath*:db/migration/V*.sql");

        assertThat(Arrays.stream(resources).map(Resource::getFilename))
                .containsExactly("V1__init_phase1_schema.sql");
    }

    @Test
    void v1ShouldDirectlyCreateOnlyCurrentTables() throws IOException {
        String sql = readMigration("V1__init_phase1_schema.sql");

        assertThat(StringUtils.countOccurrencesOf(sql, "CREATE TABLE")).isEqualTo(3);
        assertThat(sql)
                .contains("CREATE TABLE pm_user", "CREATE TABLE pm_project", "CREATE TABLE pm_project_file")
                .doesNotContain(
                        "tenant_id",
                        "pm_project_member",
                        "pm_task",
                        "pm_event_outbox",
                        "pm_project_file_upload",
                        "pm_project_file_ingest_batch",
                        "analysis_status",
                        "analysis_version",
                        "detail_ref"
                );
    }

    @Test
    void currentPersistenceEntitiesShouldNotContainTenantField() {
        List<String> fieldNames = List.of(User.class, Project.class, ProjectFile.class).stream()
                .flatMap(type -> Arrays.stream(type.getDeclaredFields()))
                .map(Field::getName)
                .toList();

        assertThat(fieldNames).doesNotContain("tenantId", "deleted", "createdBy", "updatedBy");
    }

    @Test
    void projectFileShouldNotContainAnalysisFields() {
        List<String> fieldNames = Arrays.stream(ProjectFile.class.getDeclaredFields())
                .map(Field::getName)
                .toList();

        assertThat(fieldNames).doesNotContain(
                "analysisStatus",
                "analysisVersion",
                "detailRef",
                "analysisSummary",
                "analysisKeywords",
                "analysisAttempts",
                "analyzedAt"
        );
    }

    private String readMigration(String fileName) throws IOException {
        ClassPathResource resource = new ClassPathResource("db/migration/" + fileName);
        return resource.getContentAsString(StandardCharsets.UTF_8);
    }
}
