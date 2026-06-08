package com.ning.pm.common.web;

import com.ning.pm.common.response.R;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 内部健康检查接口。
 */
@RestController
public class HealthController {

    @GetMapping("/internal/health")
    public R<Map<String, String>> health() {
        return R.success(Map.of("status", "UP"));
    }
}
