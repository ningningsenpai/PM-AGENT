package com.ning.pm.common.errorcode;

/**
 * 统一错误码枚举。
 */
public enum ErrorCode {
    SUCCESS(0, "成功"),
    PARAM_INVALID(10001, "参数不合法"),
    IDEMPOTENCY_KEY_MISSING(10002, "缺少幂等键"),
    RESOURCE_CONFLICT(10003, "资源冲突"),
    UNAUTHORIZED(20001, "未登录"),
    FORBIDDEN(20002, "无权限"),
    USER_NOT_FOUND(20003, "用户不存在"),
    PROJECT_NOT_FOUND(30001, "项目不存在"),
    TASK_NOT_FOUND(30002, "任务不存在"),
    TASK_STATUS_INVALID(30003, "任务状态流转不合法"),
    RISK_NOT_FOUND(30004, "风险不存在"),
    AGENT_SERVICE_ERROR(40001, "Agent 服务异常"),
    MODEL_CALL_FAILED(40002, "模型调用失败"),
    TOOL_CALL_FAILED(40003, "工具调用失败"),
    HUMAN_CONFIRMATION_REQUIRED(40004, "需要人工确认"),
    EXTERNAL_SERVICE_ERROR(50001, "外部服务异常"),
    SYSTEM_ERROR(90001, "系统异常");

    private final int code;
    private final String message;

    ErrorCode(int code, String message) {
        this.code = code;
        this.message = message;
    }

    public int getCode() {
        return code;
    }

    public String getMessage() {
        return message;
    }
}
