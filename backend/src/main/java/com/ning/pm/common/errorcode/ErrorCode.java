package com.ning.pm.common.errorcode;

import lombok.Getter;

/**
 * ErrorCode 是统一错误码枚举。
 *
 * @author ning
 * @date 2026-06-08
 */
@Getter
public enum ErrorCode {
    SUCCESS(0, "成功"),
    PARAM_INVALID(10001, "参数不合法"),
    RESOURCE_CONFLICT(10003, "资源冲突"),
    UNAUTHORIZED(20001, "未登录"),
    FORBIDDEN(20002, "无权限"),
    USER_NOT_FOUND(20003, "用户不存在"),
    AUTH_LOGIN_FAILED(20004, "邮箱或密码错误"),
    USER_DISABLED(20005, "用户已禁用"),
    USERNAME_EXISTS(20006, "用户名已存在"),
    PASSWORD_INVALID(20007, "原密码不正确"),
    EMAIL_EXISTS(20008, "邮箱已存在"),
    SYSTEM_FILE_ACCESS_DENIED(20009, "系统文件不允许通过公开接口访问"),
    PROJECT_NOT_FOUND(30001, "项目不存在或无权访问"),
    PROJECT_DISABLED(30002, "项目已停用"),
    FILE_NOT_FOUND(30010, "文件不存在或无权访问"),
    FILE_PATH_CONFLICT(30011, "文件重复上传"),
    FILE_STATUS_INVALID(30012, "文件当前状态不允许执行该操作"),
    FILE_BUSY(30013, "文件正在被其他请求处理"),
    FILE_TOO_LARGE(30014, "文件大小超出限制"),
    FILE_EXTENSION_NOT_ALLOWED(30015, "文件扩展名不允许上传"),
    FILE_MIME_TYPE_BLOCKED(30016, "文件内容类型不允许上传"),
    FILE_PATH_IGNORED(30017, "文件路径不允许上传"),
    FILE_STORAGE_ERROR(50001, "文件存储服务异常"),
    PROJECT_INDEX_INIT_FAILED(50002, "项目上下文索引初始化失败"),
    PROJECT_INDEX_WRITE_FAILED(50003, "项目上下文索引写入失败"),
    FILE_UPLOAD_RETRY_EXHAUSTED(50004, "文件上传重试次数已用尽"),
    FILE_RENAME_FAILED(50005, "文件重命名失败"),
    PROJECT_DELETE_FAILED(50006, "项目删除失败"),
    SYSTEM_ERROR(90001, "系统异常");

    private final int code;
    private final String message;

    ErrorCode(int code, String message) {
        this.code = code;
        this.message = message;
    }

}
