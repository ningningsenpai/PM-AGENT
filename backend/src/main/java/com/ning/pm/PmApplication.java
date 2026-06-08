package com.ning.pm;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * PmApplication 是 PM-Agent 后端服务启动类。
 *
 * @author ning
 * @date 2026-06-08
 */
@MapperScan("com.ning.pm.user.repository")
@SpringBootApplication
public class PmApplication {

    public static void main(String[] args) {
        SpringApplication.run(PmApplication.class, args);
    }
}
