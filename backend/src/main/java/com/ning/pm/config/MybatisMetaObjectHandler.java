package com.ning.pm.config;

import com.baomidou.mybatisplus.core.handlers.MetaObjectHandler;
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

    @Override
    public void insertFill(MetaObject metaObject) {
        LocalDateTime now = LocalDateTime.now();
        fillIfNull(metaObject, "createdAt", now);
        fillIfNull(metaObject, "updatedAt", now);
    }

    @Override
    public void updateFill(MetaObject metaObject) {
        fillIfNull(metaObject, "updatedAt", LocalDateTime.now());
    }

    private void fillIfNull(MetaObject metaObject, String fieldName, Object value) {
        if (value != null && getFieldValByName(fieldName, metaObject) == null) {
            setFieldValByName(fieldName, value, metaObject);
        }
    }
}
