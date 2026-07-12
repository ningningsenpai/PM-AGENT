package com.ning.pm.auth.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.auth.dto.LoginResponse;
import com.ning.pm.auth.service.AuthService;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.web.GlobalExceptionHandler;
import com.ning.pm.user.dto.UserProfileResponse;
import com.ning.pm.user.domain.UserStatus;
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
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * AuthControllerTest 验证认证接口的统一响应结构。
 *
 * @author ning
 * @date 2026-06-08
 */
class AuthControllerTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private AuthService authService;
    private MockMvc mockMvc;

    @BeforeEach
    void setUp() {
        authService = mock(AuthService.class);
        CurrentUserHolder currentUserHolder = mock(CurrentUserHolder.class);
        mockMvc = MockMvcBuilders
                .standaloneSetup(new AuthController(authService, currentUserHolder))
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Test
    void loginShouldReturnUnifiedSuccessResponse() throws Exception {
        UserProfileResponse user = new UserProfileResponse(
                1L, "dev_user", "dev@example.com", UserStatus.ENABLED, null
        );
        when(authService.login(any())).thenReturn(new LoginResponse("Authorization", "mock-token", user));

        mockMvc.perform(post("/api/v1/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(new LoginPayload("dev@example.com", "Dev123456"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.message").value("成功"))
                .andExpect(jsonPath("$.data.tokenValue").value("mock-token"))
                .andExpect(jsonPath("$.data.user.username").value("dev_user"))
                .andExpect(jsonPath("$.data.user.status").value("enabled"))
                .andExpect(jsonPath("$.data.user.passwordHash").doesNotExist())
                .andExpect(jsonPath("$.traceId", notNullValue()));

        verify(authService).login(any());
    }

    private record LoginPayload(String email, String password) {
    }
}
