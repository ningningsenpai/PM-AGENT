package com.ning.pm.project.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDate;

/**
 * Project 是项目基础信息实体。
 *
 * @author ning
 * @date 2026-06-10
 */
@Getter
@Setter
@TableName("pm_project")
public class Project extends BaseEntity {

    private String name;

    private String code;

    private String description;

    private Long ownerId;

    private String status;

    private LocalDate startDate;

    private LocalDate endDate;
}
