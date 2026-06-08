package com.ning.pm.config;

import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
import com.ning.pm.common.auth.CurrentUserHolder;
import org.apache.ibatis.reflection.MetaObject;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;

/**
 * MybatisMetaObjectHandler 负责填充业务实体通用字段。
 *
 * @author ning
 * @date 2026-06-08
 */
@Component
public class MybatisMetaObjectHandler implements MetaObjectHandler {

    private final CurrentUserHolder currentUserHolder;

    public MybatisMetaObjectHandler(CurrentUserHolder currentUserHolder) {
        this.currentUserHolder = currentUserHolder;
    }

    @Override
    public void insertFill(MetaObject metaObject) {
        LocalDateTime now = LocalDateTime.now();
        Long userId = currentUserHolder.getUserIdOrNull();

        fillIfNull(metaObject, "tenantId", 0L);
        fillIfNull(metaObject, "createdAt", now);
        fillIfNull(metaObject, "updatedAt", now);
        fillIfNull(metaObject, "createdBy", userId);
        fillIfNull(metaObject, "updatedBy", userId);
    }

    @Override
    public void updateFill(MetaObject metaObject) {
        fillIfNull(metaObject, "updatedAt", LocalDateTime.now());
        fillIfNull(metaObject, "updatedBy", currentUserHolder.getUserIdOrNull());
    }

    private void fillIfNull(MetaObject metaObject, String fieldName, Object value) {
        if (value != null && getFieldValByName(fieldName, metaObject) == null) {
            setFieldValByName(fieldName, value, metaObject);
        }
    }
}
