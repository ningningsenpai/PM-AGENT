package com.ning.pm.project.domain;

import com.ning.pm.common.exception.BizException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * SystemFilePathTest 验证固定系统文件与受控系统目录的路径约束。
 *
 * @author ning
 * @date 2026-07-13
 */
class SystemFilePathTest {

    @Test
    void fileDetailsShouldResolveControlledRelativePath() {
        String path = SystemFilePath.FILE_DETAILS.resolve("backend/auth/controller.json");

        assertThat(path).isEqualTo("file_details/backend/auth/controller.json");
    }

    @Test
    void windowsSeparatorShouldBeNormalized() {
        String path = SystemFilePath.USER_HABITS.resolve("work\\daily.json");

        assertThat(path).isEqualTo("user_habits/work/daily.json");
    }

    @Test
    void traversalPathShouldBeRejected() {
        assertThatThrownBy(() -> SystemFilePath.FILE_DETAILS.resolve("../secret.json"))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("合法相对路径");
    }

    @Test
    void indexShouldExposeFixedPath() {
        assertThat(SystemFilePath.INDEX.fixedPath()).isEqualTo("index.json");
    }
}
