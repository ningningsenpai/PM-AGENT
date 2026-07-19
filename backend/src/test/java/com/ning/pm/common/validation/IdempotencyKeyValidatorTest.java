package com.ning.pm.common.validation;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class IdempotencyKeyValidatorTest {

    @Test
    void normalizeShouldTrimValidKey() {
        assertThat(IdempotencyKeyValidator.normalize("  request-key  ")).isEqualTo("request-key");
        assertThat(IdempotencyKeyValidator.normalize("a".repeat(64))).hasSize(64);
    }

    @Test
    void normalizeShouldRejectInvalidKey() {
        assertInvalid(null);
        assertInvalid("   ");
        assertInvalid("a".repeat(65));
    }

    private void assertInvalid(String value) {
        assertThatThrownBy(() -> IdempotencyKeyValidator.normalize(value))
                .isInstanceOf(BizException.class)
                .hasMessage("X-Idempotency-Key长度必须为1到64个字符")
                .satisfies(exception -> assertThat(((BizException) exception).getErrorCode())
                        .isEqualTo(ErrorCode.PARAM_INVALID));
    }
}
