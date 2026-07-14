package com.ning.pm.project.domain;

import com.ning.pm.common.exception.BizException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * SystemFilePathTest 验证系统文件对象键的目录组成和相对路径约束。
 *
 * @author ning
 * @date 2026-07-13
 */
class SystemFilePathTest {

    @Test
    void fileDetailsShouldBuildCompleteObjectKey() {
        String objectKey = SystemFilePath.FILE_DETAILS.build(
                20L,
                10L,
                "backend/auth/controller.json"
        );

        assertThat(objectKey).isEqualTo(
                "PM-AGENT/10/20/project/context/file_details/backend/auth/controller.json"
        );
    }

    @Test
    void windowsSeparatorShouldBeNormalized() {
        String objectKey = SystemFilePath.USER_HABITS.build(
                20L,
                10L,
                "work\\daily.json"
        );

        assertThat(objectKey).isEqualTo(
                "PM-AGENT/10/20/project/context/user_habits/work/daily.json"
        );
    }

    @Test
    void traversalPathShouldBeRejected() {
        assertThatThrownBy(() -> SystemFilePath.FILE_DETAILS.build(20L, 10L, "../secret.json"))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("合法相对路径");
    }
}
