package com.ning.pm.common.web;

import cn.dev33.satoken.stp.StpUtil;
import com.ning.pm.common.trace.TraceContext;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * 请求链路追踪拦截器，负责写入 traceId 等日志字段。
 */
@Component
public class TraceInterceptor implements HandlerInterceptor {

    private static final String TRACE_HEADER = "X-Trace-Id";

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String traceId = request.getHeader(TRACE_HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = TraceContext.getTraceId();
        }
        MDC.put(TraceContext.TRACE_ID, traceId);
        MDC.put(TraceContext.TENANT_ID, "0");
        MDC.put(TraceContext.ACTION, request.getMethod() + " " + request.getRequestURI());
        MDC.put(TraceContext.USER_ID, StpUtil.isLogin() ? String.valueOf(StpUtil.getLoginIdAsLong()) : "-");
        request.setAttribute("startMs", System.currentTimeMillis());
        response.setHeader(TRACE_HEADER, traceId);
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        Object startMs = request.getAttribute("startMs");
        if (startMs instanceof Long start) {
            MDC.put(TraceContext.COST_MS, String.valueOf(System.currentTimeMillis() - start));
        }
        TraceContext.clear();
    }
}
