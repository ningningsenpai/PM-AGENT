package com.ning.pm.user.service.impl;

import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.user.converter.UserConverter;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.repository.UserMapper;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * UserServiceImplTest 验证用户基础业务逻辑。
 *
 * @author ning
 * @date 2026-06-08
 */
@ExtendWith(MockitoExtension.class)
class UserServiceImplTest {

    @Mock
    private UserMapper userMapper;

    @Mock
    private UserConverter userConverter;

    @InjectMocks
    private UserServiceImpl userService;

    @Test
    void createUserShouldFillAccountFields() {
        RegisterRequest request = new RegisterRequest("dev_user", "Dev123456", "开发用户", null, null);
        when(userMapper.selectOne(any())).thenReturn(null);
        when(userConverter.toEntity(request)).thenReturn(new User());

        userService.createUser(request, "dev_user", "hash-value");

        ArgumentCaptor<User> captor = ArgumentCaptor.forClass(User.class);
        verify(userMapper).insert(captor.capture());
        User user = captor.getValue();
        assertThat(user.getUsername()).isEqualTo("dev_user");
        assertThat(user.getPasswordHash()).isEqualTo("hash-value");
        assertThat(user.getStatus()).isEqualTo("enabled");
        assertThat(user.getTenantId()).isZero();
        assertThat(user.getDeleted()).isZero();
    }

    @Test
    void createUserShouldRejectDuplicateUsername() {
        RegisterRequest request = new RegisterRequest("dev_user", "Dev123456", "开发用户", null, null);
        when(userMapper.selectOne(any())).thenReturn(new User());

        assertThatThrownBy(() -> userService.createUser(request, "dev_user", "hash-value"))
                .isInstanceOf(BizException.class)
                .extracting("errorCode")
                .isEqualTo(ErrorCode.USERNAME_EXISTS);
    }
}
