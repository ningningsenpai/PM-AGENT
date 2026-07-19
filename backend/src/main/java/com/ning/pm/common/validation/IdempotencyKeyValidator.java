package com.ning.pm.common.validation;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;

/**
 * 统一校验并规范化 HTTP 幂等键。
 */
public final class IdempotencyKeyValidator {

    private static final int MAX_LENGTH = 64;

    private IdempotencyKeyValidator() {
    }

    public static String normalize(String value) {
        if (value == null || value.isBlank() || value.length() > MAX_LENGTH) {
            throw new BizException(ErrorCode.PARAM_INVALID, "X-Idempotency-Key长度必须为1到64个字符");
        }
        return value.trim();
    }
}
