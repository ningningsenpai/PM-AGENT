package com.ning.pm.file.service;

import com.ning.pm.common.exception.BizException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * FileFingerprintServiceTest 验证路径规范化和两级哈希规则。
 *
 * @author ning
 * @date 2026-07-12
 */
class FileFingerprintServiceTest {

    private final FileFingerprintService service = new FileFingerprintService();

    @Test
    void shouldNormalizeWindowsRelativePath() {
        assertThat(service.normalizeRelativePath("./backend\\src\\App.java"))
                .isEqualTo("backend/src/App.java");
    }

    @Test
    void quickFingerprintShouldChangeWhenPathOrMtimeChanges() {
        String original = service.quickFingerprint("src/App.java", 10, 1000);

        assertThat(service.quickFingerprint("src/NewApp.java", 10, 1000)).isNotEqualTo(original);
        assertThat(service.quickFingerprint("src/App.java", 10, 1001)).isNotEqualTo(original);
    }

    @Test
    void contentHashShouldOnlyDependOnContent() {
        assertThat(service.contentHash("same".getBytes()))
                .isEqualTo(service.contentHash("same".getBytes()));
    }

    @Test
    void shouldRejectDirectoryTraversal() {
        assertThatThrownBy(() -> service.normalizeRelativePath("../secret.txt"))
                .isInstanceOf(BizException.class);
    }
}
