package com.ning.pm.infrastructure.messaging.outbox;

import com.baomidou.mybatisplus.annotation.EnumValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

@Getter
@RequiredArgsConstructor
public enum OutboxStatus {
    PENDING("pending"),
    PUBLISHED("published");

    @EnumValue
    private final String code;
}
