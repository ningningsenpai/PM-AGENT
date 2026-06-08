package com.ning.pm.common.auth;

import cn.dev33.satoken.stp.StpUtil;
import org.springframework.stereotype.Component;

/**
 * CurrentUserHolder 封装当前登录用户读取逻辑，避免业务代码分散依赖 Sa-Token 静态 API。
 *
 * @author ning
 * @date 2026-06-08
 */
@Component
public class CurrentUserHolder {

    /**
     * 获取当前登录用户 ID；未登录时返回 null，便于基础填充逻辑兼容匿名请求。
     */
    public Long getUserIdOrNull() {
        if (!StpUtil.isLogin()) {
            return null;
        }
        return StpUtil.getLoginIdAsLong();
    }

    /**
     * 获取当前登录用户 ID；未登录时由 Sa-Token 抛出统一未登录异常。
     */
    public Long requireUserId() {
        return StpUtil.getLoginIdAsLong();
    }
}
