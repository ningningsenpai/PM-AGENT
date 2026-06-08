package com.ning.pm.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * OpenApiConfig 配置后端接口文档基础信息。
 *
 * @author ning
 * @date 2026-06-08
 */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI pmAgentOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("PM-Agent 后端接口")
                        .version("v1")
                        .description("PM-Agent 智能项目管理平台第 1 阶段后端接口"));
    }
}
