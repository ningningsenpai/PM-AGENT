package com.ning.pm.file.analysis;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/**
 * 内部服务接口使用独立共享令牌，避免复用用户登录态。
 */
@Component
@RequiredArgsConstructor
public class InternalServiceAuthenticator {

    private final AgentFileAnalysisProperties properties;

    public void requireValidToken(String actualToken) {
        String expectedToken = properties.getInternalToken();
        if (actualToken == null || expectedToken == null || expectedToken.isBlank()
                || !MessageDigest.isEqual(
                        expectedToken.getBytes(StandardCharsets.UTF_8),
                        actualToken.getBytes(StandardCharsets.UTF_8)
                )) {
            throw new BizException(ErrorCode.INTERNAL_SERVICE_UNAUTHORIZED);
        }
    }
}
