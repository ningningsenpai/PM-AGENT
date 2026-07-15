package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * ProjectFileStatus 定义项目文件的存储生命周期状态。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@RequiredArgsConstructor
public enum ProjectFileStatus {

    UPLOADING("uploading", "上传中"),
    ACTIVE("active", "可用"),
    UPDATING("updating", "覆盖更新中"),
    UPLOAD_FAILED("upload_failed", "首次上传失败"),
    VERIFY_REQUIRED("verify_required", "需要校验"),
    MISSING("missing", "源文件缺失"),
    DELETING("deleting", "删除中"),
    DELETE_FAILED("delete_failed", "删除失败");

    @EnumValue
    private final String code;
    private final String description;

    @JsonValue
    public String value() {
        return code;
    }
}
