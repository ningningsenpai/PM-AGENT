"""Agent 服务统一错误码。"""

from enum import IntEnum


class ErrorCode(IntEnum):
    """Agent 服务错误码枚举。"""

    SUCCESS = 0

    PARAM_INVALID = 10001
    IDEMPOTENCY_KEY_MISSING = 10002
    RESOURCE_CONFLICT = 10003

    UNAUTHORIZED = 20001
    FORBIDDEN = 20002
    USER_NOT_FOUND = 20003
    AUTH_LOGIN_FAILED = 20004
    USER_DISABLED = 20005
    USERNAME_EXISTS = 20006
    PASSWORD_INVALID = 20007

    AGENT_SERVICE_ERROR = 40001
    MODEL_CALL_FAILED = 40002
    TOOL_CALL_FAILED = 40003
    HUMAN_CONFIRMATION_REQUIRED = 40004
    AGENT_PARAM_ERROR = 40005
    CONTEXT_BUILD_FAILED = 40006
    STREAM_OUTPUT_FAILED = 40007
    UNSUPPORTED_OPERATION = 40008
    TOOL_TIMEOUT = 40009


ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.SUCCESS: "成功",
    ErrorCode.PARAM_INVALID: "参数不合法",
    ErrorCode.IDEMPOTENCY_KEY_MISSING: "缺少幂等键",
    ErrorCode.RESOURCE_CONFLICT: "资源冲突",
    ErrorCode.UNAUTHORIZED: "未登录",
    ErrorCode.FORBIDDEN: "无权限",
    ErrorCode.USER_NOT_FOUND: "用户不存在",
    ErrorCode.AUTH_LOGIN_FAILED: "用户名或密码错误",
    ErrorCode.USER_DISABLED: "用户已禁用",
    ErrorCode.USERNAME_EXISTS: "用户名已存在",
    ErrorCode.PASSWORD_INVALID: "原密码不正确",
    ErrorCode.AGENT_SERVICE_ERROR: "Agent 服务异常",
    ErrorCode.MODEL_CALL_FAILED: "模型调用失败",
    ErrorCode.TOOL_CALL_FAILED: "工具调用失败",
    ErrorCode.HUMAN_CONFIRMATION_REQUIRED: "需要人工确认",
    ErrorCode.AGENT_PARAM_ERROR: "Agent 参数错误",
    ErrorCode.CONTEXT_BUILD_FAILED: "上下文构建失败",
    ErrorCode.STREAM_OUTPUT_FAILED: "流式输出失败",
    ErrorCode.UNSUPPORTED_OPERATION: "不支持的操作",
    ErrorCode.TOOL_TIMEOUT: "工具调用超时",
}


def get_error_message(code: ErrorCode) -> str:
    """根据错误码获取默认中文错误信息。"""
    return ERROR_MESSAGES.get(code, "未知错误")
