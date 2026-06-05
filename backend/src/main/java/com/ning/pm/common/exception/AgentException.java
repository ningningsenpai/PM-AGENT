package com.ning.pm.common.exception;

import com.ning.pm.common.errorcode.ErrorCode;

/**
 * Agent 服务调用异常。
 */
public class AgentException extends BaseException {

    public AgentException(ErrorCode errorCode) {
        super(errorCode);
    }

    public AgentException(ErrorCode errorCode, String message) {
        super(errorCode, message);
    }
}
