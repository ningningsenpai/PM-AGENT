package com.ning.pm.config;

import cn.dev33.satoken.jwt.StpLogicJwtForSimple;
import cn.dev33.satoken.stp.StpLogic;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * SaTokenConfig 配置 Sa-Token 使用 JWT 简单模式生成登录令牌。
 *
 * @author ning
 * @date 2026-06-08
 */
@Configuration
public class SaTokenConfig {

    @Bean
    public StpLogic stpLogic() {
        return new StpLogicJwtForSimple();
    }
}
