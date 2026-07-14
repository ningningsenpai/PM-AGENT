package com.ning.pm.infrastructure.redis;

import lombok.RequiredArgsConstructor;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

/**
 * RedisIdempotencyGuard 使用 Redis 原子占位拦截有效期内的重复写请求。
 *
 * @author ning
 * @date 2026-07-13
 */
@Component
@RequiredArgsConstructor
public class RedisIdempotencyGuard {

    // redis 键值对占用值，无实际意义
    private static final String OCCUPIED_VALUE = "1";

    private final StringRedisTemplate redisTemplate;

    /**
     * 尝试占用幂等键；用户、操作范围和客户端幂等键共同确定隔离范围。
     *
     * @param userId         当前用户ID
     * @param operationScope 写操作范围
     * @param idempotencyKey 客户端幂等键
     * @return 首次占用返回true，有效期内重复占用返回false
     */
    public boolean tryAcquire(Long userId, String operationScope, String idempotencyKey) {
        RedisKeyDefinition definition = RedisKeyDefinition.IDEMPOTENCY;
        String redisKey = String.join(
                ":",
                definition.getKeyPrefix(),
                String.valueOf(userId),
                operationScope,
                idempotencyKey
        );
        return Boolean.TRUE.equals(redisTemplate.opsForValue().setIfAbsent(
                redisKey,
                OCCUPIED_VALUE,
                definition.getTtl()
        ));
    }
}
