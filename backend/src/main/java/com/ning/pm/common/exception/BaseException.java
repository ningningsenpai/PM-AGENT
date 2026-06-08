package com.ning.pm.common.exception;

import com.ning.pm.common.errorcode.ErrorCode;
import lombok.Getter;

/**
 * 业务异常基类，携带统一错误码。
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

}
