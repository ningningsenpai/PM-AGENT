package com.ning.pm.user.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.web.GlobalExceptionHandler;
import com.ning.pm.common.web.IdempotencyInterceptor;
import com.ning.pm.user.dto.UpdateUserProfileRequest;
import com.ning.pm.user.dto.UserProfileResponse;
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
 * UserControllerTest 验证当前用户资料写接口响应结构与幂等键校验。
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
                .addInterceptors(new IdempotencyInterceptor())
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void updateMeShouldRequireIdempotencyKey() throws Exception {
        mockMvc.perform(put("/api/v1/users/me")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new UpdateUserProfileRequest("开发用户", null, null))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(10002))
                .andExpect(jsonPath("$.message").value("缺少幂等键"))
                .andExpect(jsonPath("$.traceId", notNullValue()));
    }

    @Test
    void updateMeShouldReturnUnifiedSuccessResponse() throws Exception {
        UserProfileResponse response = new UserProfileResponse(1L, 0L, "dev_user", "开发用户", "dev@example.com", null, "enabled", null);
        when(userService.updateCurrentUserProfile(any())).thenReturn(response);

        mockMvc.perform(put("/api/v1/users/me")
                        .header("X-Idempotency-Key", "idem-user-001")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new UpdateUserProfileRequest("开发用户", "dev@example.com", null))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.message").value("成功"))
                .andExpect(jsonPath("$.data.displayName").value("开发用户"))
                .andExpect(jsonPath("$.traceId", notNullValue()));

        verify(userService).updateCurrentUserProfile(any());
    }
}
