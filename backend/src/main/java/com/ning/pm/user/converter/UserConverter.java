package com.ning.pm.user.converter;

import com.ning.pm.auth.dto.RegisterRequest;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.dto.UserProfileResponse;
import org.mapstruct.Mapper;
import org.mapstruct.Mapping;
import org.mapstruct.ReportingPolicy;

/**
 * UserConverter 负责用户实体与接口对象之间的字段转换。
 *
 * @author ning
 * @date 2026-06-08
 */
@Mapper(componentModel = "spring", unmappedTargetPolicy = ReportingPolicy.ERROR)
public interface UserConverter {

    @Mapping(target = "id", ignore = true)
    @Mapping(target = "tenantId", ignore = true)
    @Mapping(target = "createdBy", ignore = true)
    @Mapping(target = "createdAt", ignore = true)
    @Mapping(target = "updatedBy", ignore = true)
    @Mapping(target = "updatedAt", ignore = true)
    @Mapping(target = "deleted", ignore = true)
    @Mapping(target = "passwordHash", ignore = true)
    @Mapping(target = "status", ignore = true)
    @Mapping(target = "lastLoginAt", ignore = true)
    User toEntity(RegisterRequest request);

    UserProfileResponse toProfileResponse(User user);
}
