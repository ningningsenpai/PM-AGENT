package com.ning.pm.common.exception;

import com.ning.pm.common.errorcode.ErrorCode;

/**
 * BizException 表示可预期的业务规则异常。
 *
 * @author ning
 * @date 2026-07-12
 */
public class BizException extends BaseException {

    public BizException(ErrorCode errorCode) {
        super(errorCode);
    }

    public BizException(ErrorCode errorCode, String message) {
        super(errorCode, message);
    }
}
