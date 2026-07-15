package com.ning.demo.student.common;

/**
 * ApiResponse：定义 Demo 接口的统一响应结构。
 *
 * @author ning
 * @date 2026-07-11
 */
public record ApiResponse<T>(int code, String message, T data, String traceId) {

    public static <T> ApiResponse<T> success(T data, String traceId) {
        return new ApiResponse<>(0, "成功", data, traceId);
    }

    public static <T> ApiResponse<T> error(int code, String message, String traceId) {
        return new ApiResponse<>(code, message, null, traceId);
    }
}

