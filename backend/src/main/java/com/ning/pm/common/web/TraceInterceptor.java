package com.ning.pm.common.web;

import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.trace.TraceContext;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.slf4j.MDC;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

/**
 * TraceInterceptor 负责初始化请求链路字段并输出统一访问日志。
 *
 * @author ning
 * @date 2026-07-12
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class TraceInterceptor implements HandlerInterceptor {

    private static final String TRACE_HEADER = "X-Trace-Id";
    private final CurrentUserHolder currentUserHolder;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String traceId = request.getHeader(TRACE_HEADER);
        if (traceId == null || traceId.isBlank()) {
            traceId = TraceContext.getTraceId();
        }
        MDC.put(TraceContext.TRACE_ID, traceId);
        MDC.put(TraceContext.ACTION, request.getMethod() + " " + request.getRequestURI());
        Long userId = currentUserHolder.getUserIdOrNull();
        MDC.put(TraceContext.USER_ID, userId == null ? "-" : String.valueOf(userId));
        request.setAttribute("startMs", System.currentTimeMillis());
        response.setHeader(TRACE_HEADER, traceId);
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        Object startMs = request.getAttribute("startMs");
        long costMs = startMs instanceof Long start ? System.currentTimeMillis() - start : 0L;
        MDC.put(TraceContext.COST_MS, String.valueOf(costMs));
        try {
            log.info("请求处理完成 method={} path={} status={} costMs={}",
                    request.getMethod(), request.getRequestURI(), response.getStatus(), costMs);
        } finally {
            TraceContext.clear();
        }
    }
}
