package com.ning.pm.task.domain;

import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Getter;
import lombok.Setter;

import java.time.LocalDateTime;

/**
 * TaskStatusLog 是任务状态变更追加日志，不参与逻辑删除。
 *
 * @author ning
 * @date 2026-06-10
 */
@Getter
@Setter
@TableName("pm_task_status_log")
public class TaskStatusLog {

    @TableId(type = IdType.AUTO)
    private Long id;

    private Long tenantId;

    private Long taskId;

    private String fromStatus;

    private String toStatus;

    private Long operatorId;

    private String source;

    private String reason;

    private String traceId;

    private LocalDateTime createdAt;
}
