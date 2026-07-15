package com.ning.pm.common.web;

import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.response.R;
import com.ning.pm.common.trace.TraceContext;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * TraceInterceptorTest 验证请求头、响应体和 MDC 使用同一 traceId。
 *
 * @author ning
 * @date 2026-07-12
 */
class TraceInterceptorTest {

    @AfterEach
    void clearMdc() {
        MDC.clear();
    }

    @Test
    void shouldPropagateTraceIdAndClearMdcAfterRequest() throws Exception {
        CurrentUserHolder currentUserHolder = mock(CurrentUserHolder.class);
        when(currentUserHolder.getUserIdOrNull()).thenReturn(1L);
        TraceInterceptor interceptor = new TraceInterceptor(currentUserHolder);
        MockHttpServletRequest request = new MockHttpServletRequest("GET", "/internal/health");
        MockHttpServletResponse response = new MockHttpServletResponse();
        request.addHeader("X-Trace-Id", "trace-test-001");

        assertThat(interceptor.preHandle(request, response, new Object())).isTrue();
        assertThat(response.getHeader("X-Trace-Id")).isEqualTo("trace-test-001");
        assertThat(R.success(null).traceId()).isEqualTo("trace-test-001");
        assertThat(MDC.get(TraceContext.USER_ID)).isEqualTo("1");

        interceptor.afterCompletion(request, response, new Object(), null);

        assertThat(MDC.get(TraceContext.TRACE_ID)).isNull();
    }
}
