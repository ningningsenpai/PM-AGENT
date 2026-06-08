package com.ning.pm.user.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * User 是 PM-Agent 登录用户实体，对应用户账号与基础资料。
 *
 * @author ning
 * @date 2026-06-08
 */
@Getter
@Setter
@TableName("pm_user")
public class User extends BaseEntity {

    private String username;

    private String passwordHash;

    private String displayName;

    private String email;

    private String mobile;

    private String status;

    private LocalDateTime lastLoginAt;
}
