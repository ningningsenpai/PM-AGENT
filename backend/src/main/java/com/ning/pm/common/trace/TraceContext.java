package com.ning.pm.common.trace;

import cn.hutool.core.util.IdUtil;
import org.slf4j.MDC;

/**
 * TraceContext 管理请求链路日志使用的 MDC 字段。
 *
 * @author ning
 * @date 2026-07-12
 */
public final class TraceContext {

    public static final String TRACE_ID = "traceId";
    public static final String USER_ID = "userId";
    public static final String ACTION = "action";
    public static final String COST_MS = "costMs";

    private TraceContext() {
    }

    public static String getTraceId() {
        String traceId = MDC.get(TRACE_ID);
        if (traceId == null || traceId.isBlank()) {
            traceId = IdUtil.fastSimpleUUID();
            MDC.put(TRACE_ID, traceId);
        }
        return traceId;
    }

    public static void clear() {
        MDC.clear();
    }
}
