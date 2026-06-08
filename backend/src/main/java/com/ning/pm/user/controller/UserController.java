package com.ning.pm.user.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.response.R;
import com.ning.pm.user.dto.UserProfileResponse;
import com.ning.pm.user.service.UserService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * UserController 提供当前账户资料查询接口。
 *
 * @author ning
 * @date 2026-06-08
 */
@RestController
@RequestMapping("/api/v1/users")
public class UserController {

    private static final Logger log = LoggerFactory.getLogger(UserController.class);

    private final UserService userService;
    private final CurrentUserHolder currentUserHolder;

    public UserController(UserService userService, CurrentUserHolder currentUserHolder) {
        this.userService = userService;
        this.currentUserHolder = currentUserHolder;
    }

    /** 查询当前登录用户的账户资料。 */
    @SaCheckLogin
    @GetMapping("/me")
    public R<UserProfileResponse> me() {
        Long userId = currentUserHolder.requireUserId();
        log.info("查询当前账户信息 userId={}", userId);
        return R.success(userService.getCurrentUserProfile());
    }
}
