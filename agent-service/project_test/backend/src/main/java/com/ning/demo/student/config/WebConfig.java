package com.ning.demo.student.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * WebConfig：配置 Demo 前后端本地联调的跨域策略。
 *
 * @author ning
 * @date 2026-07-11
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        // 识别测试点：任意来源跨域仅为 Demo 联调便利，生产环境必须限制可信域名。
        registry.addMapping("/api/**").allowedOriginPatterns("*").allowedMethods("*");
    }
}

