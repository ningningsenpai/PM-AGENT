package com.ning.demo.student.student;

import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/** Demo 级幂等键登记器；生产实现应迁移到共享存储。 */
@Component
public class IdempotencyRegistry {

    private static final Duration RETENTION = Duration.ofMinutes(10);
    private final Map<String, Instant> accepted = new ConcurrentHashMap<>();

    public boolean register(String key) {
        Instant now = Instant.now();
        accepted.entrySet().removeIf(entry -> entry.getValue().plus(RETENTION).isBefore(now));
        return accepted.putIfAbsent(key, now) == null;
    }
}

