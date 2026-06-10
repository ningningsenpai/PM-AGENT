package com.ning.pm.project.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * ProjectMember 是项目成员关系实体。
 *
 * @author ning
 * @date 2026-06-10
 */
@Getter
@Setter
@TableName("pm_project_member")
public class ProjectMember extends BaseEntity {

    private Long projectId;

    private Long userId;

    private String projectRole;

    private LocalDateTime joinedAt;
}
