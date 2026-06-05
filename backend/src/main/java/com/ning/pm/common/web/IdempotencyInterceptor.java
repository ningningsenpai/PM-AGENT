package com.ning.pm.common.web;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.Set;

/**
 * 幂等键拦截器，第 1 阶段先校验写接口必须携带幂等键。
 */
@Component
public class IdempotencyInterceptor implements HandlerInterceptor {

    private static final String IDEMPOTENCY_HEADER = "X-Idempotency-Key";
    private static final Set<String> WRITE_METHODS = Set.of("POST", "PUT", "PATCH", "DELETE");

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        if (!request.getRequestURI().startsWith("/api/v1/")) {
            return true;
        }
        if (!WRITE_METHODS.contains(request.getMethod())) {
            return true;
        }
        String key = request.getHeader(IDEMPOTENCY_HEADER);
        if (key == null || key.isBlank()) {
            throw new BizException(ErrorCode.IDEMPOTENCY_KEY_MISSING);
        }
        return true;
    }
}
