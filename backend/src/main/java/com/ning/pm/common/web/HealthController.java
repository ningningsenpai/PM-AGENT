package com.ning.pm.common.web;

import com.ning.pm.common.response.R;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * HealthController 提供内部健康检查接口。
 *
 * @author ning
 * @date 2026-07-12
 */
@RestController
@Slf4j
public class HealthController {

    @GetMapping("/internal/health")
    public R<Map<String, String>> health() {
        log.info("健康检查通过");
        return R.success(Map.of("status", "UP"));
    }
}
