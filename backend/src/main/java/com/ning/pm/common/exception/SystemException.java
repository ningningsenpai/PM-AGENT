package com.ning.pm.common.exception;

import com.ning.pm.common.errorcode.ErrorCode;

/**
 * SystemException 表示需要记录堆栈的系统异常。
 *
 * @author ning
 * @date 2026-07-12
 */
public class SystemException extends BaseException {

    public SystemException(ErrorCode errorCode) {
        super(errorCode);
    }

    public SystemException(ErrorCode errorCode, String message) {
        super(errorCode, message);
    }

    public SystemException(ErrorCode errorCode, Throwable cause) {
        super(errorCode, errorCode.getMessage(), cause);
    }

    public SystemException(ErrorCode errorCode, String message, Throwable cause) {
        super(errorCode, message, cause);
    }
}
