package com.ning.pm.common.trace;

import cn.hutool.core.util.IdUtil;
import org.slf4j.MDC;

/**
 * 链路追踪上下文工具。
 */
public final class TraceContext {

    public static final String TRACE_ID = "traceId";
    public static final String USER_ID = "userId";
    public static final String TENANT_ID = "tenantId";
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
