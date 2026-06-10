package com.ning.pm.user.service.impl;

import cn.hutool.crypto.digest.BCrypt;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.user.converter.UserConverter;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.dto.ChangePasswordRequest;
import com.ning.pm.user.dto.UpdateUserProfileRequest;
import com.ning.pm.user.dto.UserProfileResponse;
import com.ning.pm.user.repository.UserMapper;
import com.ning.pm.user.service.UserService;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

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
        User user = requireCurrentUser();
        return userConverter.toProfileResponse(user);
    }

    /** 修改当前登录用户的基础资料。 */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public UserProfileResponse updateCurrentUserProfile(UpdateUserProfileRequest request) {
        User user = requireCurrentUser();
        userConverter.updateEntity(user, request);
        userMapper.updateById(user);
        return userConverter.toProfileResponse(user);
    }

    /** 修改当前登录用户密码；密码仅写入哈希，不记录明文日志。 */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void changeCurrentUserPassword(ChangePasswordRequest request) {
        User user = requireCurrentUser();
        if (!BCrypt.checkpw(request.oldPassword(), user.getPasswordHash())) {
            throw new BizException(ErrorCode.PASSWORD_INVALID);
        }
        if (!request.newPassword().equals(request.confirmPassword())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "两次输入的新密码不一致");
        }
        if (BCrypt.checkpw(request.newPassword(), user.getPasswordHash())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "新密码不能与原密码相同");
        }
        user.setPasswordHash(BCrypt.hashpw(request.newPassword(), BCrypt.gensalt()));
        userMapper.updateById(user);
    }

    @Override
    public void updateLastLoginAt(Long userId, LocalDateTime loginAt) {
        userMapper.update(null, new LambdaUpdateWrapper<User>()
                .eq(User::getId, userId)
                .set(User::getLastLoginAt, loginAt));
    }

    private User requireCurrentUser() {
        Long userId = currentUserHolder.requireUserId();
        User user = userMapper.selectById(userId);
        if (user == null || Integer.valueOf(1).equals(user.getDeleted())) {
            throw new BizException(ErrorCode.USER_NOT_FOUND);
        }
        return user;
    }
}
