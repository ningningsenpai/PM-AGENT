package com.ning.pm.infrastructure.redis;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;

import java.time.Duration;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * RedisIdempotencyGuardTest 验证幂等键的隔离维度和两分钟有效期。
 *
 * @author ning
 * @date 2026-07-13
 */
@ExtendWith(MockitoExtension.class)
class RedisIdempotencyGuardTest {

    @Mock
    private StringRedisTemplate redisTemplate;
    @Mock
    private ValueOperations<String, String> valueOperations;

    private RedisIdempotencyGuard guard;

    @BeforeEach
    void setUp() {
        guard = new RedisIdempotencyGuard(redisTemplate);
        when(redisTemplate.opsForValue()).thenReturn(valueOperations);
    }

    @Test
    void firstRequestShouldAcquireKeyForTwoMinutes() {
        when(valueOperations.setIfAbsent(
                "pm-agent:idempotency:10:file:create:20:project:request-key",
                "1",
                Duration.ofMinutes(2)
        )).thenReturn(true);

        boolean acquired = guard.tryAcquire(10L, "file:create:20:project", "request-key");

        assertThat(acquired).isTrue();
        verify(valueOperations).setIfAbsent(
                "pm-agent:idempotency:10:file:create:20:project:request-key",
                "1",
                Duration.ofMinutes(2)
        );
    }

    @Test
    void duplicateRequestShouldBeRejected() {
        when(valueOperations.setIfAbsent(
                "pm-agent:idempotency:10:file:content:20:30:request-key",
                "1",
                Duration.ofMinutes(2)
        )).thenReturn(false);

        boolean acquired = guard.tryAcquire(10L, "file:content:20:30", "request-key");

        assertThat(acquired).isFalse();
    }
}
