package com.ning.pm.infrastructure.redis;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

import java.time.Duration;

/**
 * RedisKeyDefinition 集中定义项目自管 Redis 键的名称前缀和过期时间。
 * Sa-Token 内部键由框架维护，不在此重复声明。
 *
 * @author ning
 * @date 2026-07-13
 */
@Getter
@RequiredArgsConstructor
public enum RedisKeyDefinition {

    IDEMPOTENCY("pm-agent:idempotency", Duration.ofMinutes(2));

    private final String keyPrefix;
    private final Duration ttl;
}
