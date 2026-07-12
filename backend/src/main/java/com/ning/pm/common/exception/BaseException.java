package com.ning.pm.common.exception;

import com.ning.pm.common.errorcode.ErrorCode;
import lombok.Getter;

/**
 * BaseException 是携带统一错误码的异常基类。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
public class BaseException extends RuntimeException {

    private final ErrorCode errorCode;

    public BaseException(ErrorCode errorCode) {
        super(errorCode.getMessage());
        this.errorCode = errorCode;
    }

    public BaseException(ErrorCode errorCode, String message) {
        super(message);
        this.errorCode = errorCode;
    }

    public BaseException(ErrorCode errorCode, String message, Throwable cause) {
        super(message, cause);
        this.errorCode = errorCode;
    }

}
