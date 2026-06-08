package com.ning.pm.common.response;

import com.ning.pm.common.trace.TraceContext;

/**
 * 统一接口响应结构。
 */
public record R<T>(Integer code, String message, T data, String traceId) {

    public static <T> R<T> success(T data) {
        return new R<>(0, "成功", data, TraceContext.getTraceId());
    }

    public static <T> R<T> fail(Integer code, String message) {
        return new R<>(code, message, null, TraceContext.getTraceId());
    }
}
