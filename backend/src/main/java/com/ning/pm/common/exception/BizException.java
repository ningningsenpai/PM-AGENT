package com.ning.pm.common.exception;

import com.ning.pm.common.errorcode.ErrorCode;

/**
 * 普通业务异常。
 */
public class BizException extends BaseException {

    public BizException(ErrorCode errorCode) {
        super(errorCode);
    }

    public BizException(ErrorCode errorCode, String message) {
        super(errorCode, message);
    }
}
