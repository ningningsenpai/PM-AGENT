package com.ning.pm.config;

import com.ning.pm.common.web.IdempotencyInterceptor;
import com.ning.pm.common.web.TraceInterceptor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * Web MVC 配置，注册全局拦截器。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final TraceInterceptor traceInterceptor;
    private final IdempotencyInterceptor idempotencyInterceptor;

    public WebMvcConfig(TraceInterceptor traceInterceptor, IdempotencyInterceptor idempotencyInterceptor) {
        this.traceInterceptor = traceInterceptor;
        this.idempotencyInterceptor = idempotencyInterceptor;
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(traceInterceptor).addPathPatterns("/**");
        registry.addInterceptor(idempotencyInterceptor).addPathPatterns("/api/v1/**");
    }
}
