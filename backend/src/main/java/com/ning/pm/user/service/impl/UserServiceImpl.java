package com.ning.pm.user.service.impl;

import cn.hutool.core.date.DateTime;
import cn.hutool.crypto.digest.BCrypt;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.user.converter.UserConverter;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.domain.UserStatus;
import com.ning.pm.user.dto.ChangePasswordRequest;
import com.ning.pm.user.dto.UpdateUserProfileRequest;
import com.ning.pm.user.dto.UserProfileResponse;
import com.ning.pm.user.repository.UserMapper;
import com.ning.pm.user.service.UserService;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Locale;

/**
 * UserServiceImpl 实现用户资料与账号数据的基础业务能力。
 *
 * @author ning
 * @date 2026-06-08
 */
@Service
@RequiredArgsConstructor
public class UserServiceImpl implements UserService {

    private final UserMapper userMapper;
    private final UserConverter userConverter;
    private final CurrentUserHolder currentUserHolder;

    /** 创建用户；用户名和邮箱唯一索引负责处理并发注册。 */
    @Override
    public User createUser(RegisterRequest request, String username, String email, String passwordHash, LocalDateTime lastLoginInAt) {
        validateUniqueFields(null, username, email);

        User user = userConverter.toEntity(request);
        user.setUsername(username);
        user.setEmail(email);
        user.setPasswordHash(passwordHash);
        user.setLastLoginAt(lastLoginInAt);
        user.setStatus(UserStatus.ENABLED);

        try {
            userMapper.insert(user);
        } catch (DuplicateKeyException exception) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "用户名或邮箱已存在");
        }
        return user;
    }

    @Override
    public User findByEmail(String email) {
        return userMapper.selectOne(new LambdaQueryWrapper<User>()
                .eq(User::getEmail, email)
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
        String username = normalize(request.username());
        String email = normalize(request.email());
        validateUniqueFields(user.getId(), username, email);
        userConverter.updateEntity(user, request);
        user.setUsername(username);
        user.setEmail(email);
        try {
            userMapper.updateById(user);
        } catch (DuplicateKeyException exception) {
            throw new BizException(ErrorCode.RESOURCE_CONFLICT, "用户名或邮箱已存在");
        }
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
        if (user == null) {
            throw new BizException(ErrorCode.USER_NOT_FOUND);
        }
        return user;
    }

    private void validateUniqueFields(Long excludedUserId, String username, String email) {
        long usernameCount = userMapper.selectCount(new LambdaQueryWrapper<User>()
                .eq(User::getUsername, username)
                .ne(excludedUserId != null, User::getId, excludedUserId));
        if (usernameCount > 0) {
            throw new BizException(ErrorCode.USERNAME_EXISTS);
        }

        long emailCount = userMapper.selectCount(new LambdaQueryWrapper<User>()
                .eq(User::getEmail, email)
                .ne(excludedUserId != null, User::getId, excludedUserId));
        if (emailCount > 0) {
            throw new BizException(ErrorCode.EMAIL_EXISTS);
        }
    }

    private String normalize(String value) {
        return value.trim().toLowerCase(Locale.ROOT);
    }
}
