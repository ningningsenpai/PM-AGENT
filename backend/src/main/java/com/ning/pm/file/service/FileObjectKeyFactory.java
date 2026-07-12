package com.ning.pm.file.service;

import com.ning.pm.file.enums.FileBusinessType;
import org.springframework.stereotype.Component;

/**
 * FileObjectKeyFactory 生成不受文件名和逻辑路径变化影响的稳定对象键。
 *
 * @author ning
 * @date 2026-07-12
 */
@Component
public class FileObjectKeyFactory {

    public String build(Long ownerUserId, Long projectId, FileBusinessType businessType, Long fileId) {
        return "PM-AGENT/%d/%d/%s/%d".formatted(
                ownerUserId,
                projectId,
                businessType.getCode(),
                fileId
        );
    }
}
