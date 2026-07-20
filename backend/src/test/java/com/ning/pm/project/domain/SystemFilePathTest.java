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
    void windowsSeparatorShouldBeNormalized() {
        String path = SystemFilePath.USER_HABITS.resolve("work\\daily.json");

        assertThat(path).isEqualTo("user_habits/work/daily.json");
    }

    @Test
    void traversalPathShouldBeRejected() {
        assertThatThrownBy(() -> SystemFilePath.USER_HABITS.resolve("../secret.json"))
                .isInstanceOf(BizException.class)
                .hasMessageContaining("合法相对路径");
    }

    @Test
    void indexShouldExposeFixedPath() {
        assertThat(SystemFilePath.INDEX.fixedPath()).isEqualTo("index.json");
    }
}
