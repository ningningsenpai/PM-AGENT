package com.ning.pm.task.domain;

import com.baomidou.mybatisplus.annotation.TableName;
import com.ning.pm.common.domain.BaseEntity;
import lombok.Getter;
import lombok.Setter;

import java.math.BigDecimal;
import java.time.LocalDate;

/**
 * Task 是项目任务实体。
 *
 * @author ning
 * @date 2026-06-10
 */
@Getter
@Setter
@TableName("pm_task")
public class Task extends BaseEntity {

    private Long projectId;

    private Long requirementId;

    private Long iterationId;

    private String title;

    private String description;

    private Long assigneeId;

    private String status;

    private String priority;

    private LocalDate dueDate;

    private BigDecimal estimatedHours;

    private BigDecimal actualHours;
}
