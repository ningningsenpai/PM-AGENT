package com.ning.pm.file.enums;

import com.baomidou.mybatisplus.annotation.EnumValue;
import com.fasterxml.jackson.annotation.JsonValue;
import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * FileChangeAction 定义文件同步后的处理动作。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@RequiredArgsConstructor
public enum FileChangeAction {

    UNCHANGED("unchanged", "未变化"),
    CREATE("create", "新增"),
    METADATA_UPDATE("metadata_update", "元信息更新"),
    PATH_MOVE("path_move", "路径移动"),
    CONTENT_OVERWRITE("content_overwrite", "内容覆盖"),
    MISSING("missing", "源文件缺失"),
    DELETE("delete", "删除");

    @EnumValue
    private final String code;
    private final String description;

    @JsonValue
    public String value() {
        return code;
    }
}
