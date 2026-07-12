package com.ning.pm.project.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import lombok.Getter;
import lombok.Setter;

/**
 * Project 表示用户拥有的最小项目文件归属空间。
 *
 * @author ning
 * @date 2026-07-12
 */
@Getter
@Setter
@TableName("pm_project")
public class Project extends BaseEntity {

    private Long ownerUserId;
    private String projectName;
    private ProjectStatus status;
}
