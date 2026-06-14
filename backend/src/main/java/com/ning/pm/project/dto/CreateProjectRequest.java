package com.ning.pm.project.dto;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

import java.time.LocalDate;

/**
 * CreateProjectRequest 表示创建项目请求。
 *
 * @author ning
 * @date 2026-06-10
 */
public record CreateProjectRequest(
        @NotBlank(message = "项目名称不能为空")
        @Size(max = 128, message = "项目名称长度不能超过 128 个字符")
        String name,

        @Size(max = 64, message = "项目编码长度不能超过 64 个字符")
        String code,

        String description,

        LocalDate startDate,

        LocalDate endDate
) {

    @AssertTrue(message = "项目结束日期不能早于开始日期")
    public boolean isDateRangeValid() {
        return startDate == null || endDate == null || !endDate.isBefore(startDate);
    }
}
