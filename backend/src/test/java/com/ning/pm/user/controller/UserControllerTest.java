package com.ning.pm.user.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.web.GlobalExceptionHandler;
import com.ning.pm.user.dto.UpdateUserProfileRequest;
import com.ning.pm.user.dto.UserProfileResponse;
import com.ning.pm.user.domain.UserStatus;
import com.ning.pm.user.service.UserService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.hamcrest.Matchers.notNullValue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * UserControllerTest 验证当前用户资料写接口的统一响应结构。
 *
 * @author ning
 * @date 2026-06-10
 */
class UserControllerTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private UserService userService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        userService = mock(UserService.class);
        CurrentUserHolder currentUserHolder = mock(CurrentUserHolder.class);
        when(currentUserHolder.requireUserId()).thenReturn(1L);
        mockMvc = MockMvcBuilders
                .standaloneSetup(new UserController(userService, currentUserHolder))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void updateMeShouldReturnUnifiedSuccessResponse() throws Exception {
        UserProfileResponse response = new UserProfileResponse(
                1L, "dev_user", "dev@example.com", UserStatus.ENABLED, null
        );
        when(userService.updateCurrentUserProfile(any())).thenReturn(response);

        mockMvc.perform(put("/api/v1/users/me")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new UpdateUserProfileRequest("dev_user", "dev@example.com"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.message").value("成功"))
                .andExpect(jsonPath("$.data.username").value("dev_user"))
                .andExpect(jsonPath("$.data.email").value("dev@example.com"))
                .andExpect(jsonPath("$.data.status").value("enabled"))
                .andExpect(jsonPath("$.traceId", notNullValue()));

        verify(userService).updateCurrentUserProfile(any());
    }
}
