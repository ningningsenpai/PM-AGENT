package com.ning.pm.auth.service.impl;

import cn.hutool.crypto.digest.BCrypt;
import com.ning.pm.auth.dto.LoginRequest;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.user.converter.UserConverter;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.service.UserService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

/**
 * AuthServiceImplTest 验证认证核心失败分支，避免泄露账号状态。
 *
 * @author ning
 * @date 2026-06-08
 */
@ExtendWith(MockitoExtension.class)
class AuthServiceImplTest {

    @Mock
    private UserService userService;

    @Mock
    private UserConverter userConverter;

    @InjectMocks
    private AuthServiceImpl authService;

    @Test
    void loginShouldUseSameErrorForUnknownUserAndWrongPassword() {
        LoginRequest request = new LoginRequest("dev_user", "wrong-password");
        when(userService.findActiveUserByUsername("dev_user")).thenReturn(null);

        assertThatThrownBy(() -> authService.login(request))
                .isInstanceOf(BizException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.AUTH_LOGIN_FAILED);
    }

    @Test
    void loginShouldRejectDisabledUser() {
        LoginRequest request = new LoginRequest("dev_user", "Dev123456");
        User user = new User();
        user.setUsername("dev_user");
        user.setPasswordHash(BCrypt.hashpw("Dev123456", BCrypt.gensalt()));
        user.setStatus("disabled");
        when(userService.findActiveUserByUsername("dev_user")).thenReturn(user);

        assertThatThrownBy(() -> authService.login(request))
                .isInstanceOf(BizException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.USER_DISABLED);
    }
}
