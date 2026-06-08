package com.ning.pm.user.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.user.converter.UserConverter;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.dto.UserProfileResponse;
import com.ning.pm.user.repository.UserMapper;
import com.ning.pm.user.service.UserService;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;

/**
 * UserServiceImpl 实现用户资料与账号数据的基础业务能力。
 *
 * @author ning
 * @date 2026-06-08
 */
@Service
public class UserServiceImpl implements UserService {

    private static final long DEFAULT_TENANT_ID = 0L;
    private static final String STATUS_ENABLED = "enabled";

    private final UserMapper userMapper;
    private final UserConverter userConverter;
    private final CurrentUserHolder currentUserHolder;

    public UserServiceImpl(UserMapper userMapper, UserConverter userConverter, CurrentUserHolder currentUserHolder) {
        this.userMapper = userMapper;
        this.userConverter = userConverter;
        this.currentUserHolder = currentUserHolder;
    }

    /**
     * 创建启用状态用户；用户名唯一性由数据库索引兜底，避免并发注册产生重复账号。
     */
    @Override
    public User createUser(RegisterRequest request, String username, String passwordHash) {
        if (findActiveUserByUsername(username) != null) {
            throw new BizException(ErrorCode.USERNAME_EXISTS);
        }

        User user = userConverter.toEntity(request);
        user.setUsername(username);
        user.setPasswordHash(passwordHash);
        user.setStatus(STATUS_ENABLED);
        user.setTenantId(DEFAULT_TENANT_ID);
        user.setDeleted(0);

        try {
            userMapper.insert(user);
        } catch (DuplicateKeyException exception) {
            throw new BizException(ErrorCode.USERNAME_EXISTS);
        }
        return user;
    }

    @Override
    public User findActiveUserByUsername(String username) {
        return userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getTenantId, DEFAULT_TENANT_ID)
                .eq(User::getUsername, username)
                .eq(User::getDeleted, 0)
                .last("LIMIT 1"));
    }

    @Override
    public UserProfileResponse getCurrentUserProfile() {
        Long userId = currentUserHolder.requireUserId();
        User user = userMapper.selectById(userId);
        if (user == null || Integer.valueOf(1).equals(user.getDeleted())) {
            throw new BizException(ErrorCode.USER_NOT_FOUND);
        }
        return userConverter.toProfileResponse(user);
    }

    @Override
    public void updateLastLoginAt(Long userId, LocalDateTime loginAt) {
        userMapper.update(null, new LambdaUpdateWrapper<User>()
                .eq(User::getId, userId)
                .set(User::getLastLoginAt, loginAt));
    }
}
