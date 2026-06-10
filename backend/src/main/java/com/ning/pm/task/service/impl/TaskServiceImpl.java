package com.ning.pm.task.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ning.pm.common.auth.CurrentUserHolder;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.BizException;
import com.ning.pm.common.trace.TraceContext;
import com.ning.pm.project.domain.Project;
import com.ning.pm.project.domain.ProjectStatus;
import com.ning.pm.project.service.ProjectService;
import com.ning.pm.task.converter.TaskConverter;
import com.ning.pm.task.domain.Task;
import com.ning.pm.task.domain.TaskPriority;
import com.ning.pm.task.domain.TaskStatus;
import com.ning.pm.task.domain.TaskStatusLog;
import com.ning.pm.task.domain.TaskStatusLogSource;
import com.ning.pm.task.dto.CreateTaskRequest;
import com.ning.pm.task.dto.TaskQueryRequest;
import com.ning.pm.task.dto.TaskResponse;
import com.ning.pm.task.dto.UpdateTaskRequest;
import com.ning.pm.task.dto.UpdateTaskStatusRequest;
import com.ning.pm.task.repository.TaskMapper;
import com.ning.pm.task.repository.TaskStatusLogMapper;
import com.ning.pm.task.service.TaskService;
import com.ning.pm.user.domain.User;
import com.ning.pm.user.repository.UserMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * TaskServiceImpl 实现任务管理基础业务能力。
 *
 * @author ning
 * @date 2026-06-10
 */
@Service
public class TaskServiceImpl implements TaskService {

    private static final Logger log = LoggerFactory.getLogger(TaskServiceImpl.class);
    private static final long DEFAULT_TENANT_ID = 0L;
    private static final String STATUS_ENABLED = "enabled";

    private final TaskMapper taskMapper;
    private final TaskStatusLogMapper taskStatusLogMapper;
    private final TaskConverter taskConverter;
    private final ProjectService projectService;
    private final UserMapper userMapper;
    private final CurrentUserHolder currentUserHolder;

    public TaskServiceImpl(TaskMapper taskMapper,
                           TaskStatusLogMapper taskStatusLogMapper,
                           TaskConverter taskConverter,
                           ProjectService projectService,
                           UserMapper userMapper,
                           CurrentUserHolder currentUserHolder) {
        this.taskMapper = taskMapper;
        this.taskStatusLogMapper = taskStatusLogMapper;
        this.taskConverter = taskConverter;
        this.projectService = projectService;
        this.userMapper = userMapper;
        this.currentUserHolder = currentUserHolder;
    }

    /** 创建任务并写入初始状态日志。 */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public TaskResponse createTask(CreateTaskRequest request) {
        Long userId = currentUserHolder.requireUserId();
        Project project = projectService.requireAccessibleProject(request.projectId(), userId);
        if (ProjectStatus.cannotCreateTask(project.getStatus())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "已完成或已归档项目不能新增任务");
        }
        validateAssignee(request.assigneeId());
        String priority = normalizePriority(request.priority());

        Task task = taskConverter.toEntity(request);
        task.setTenantId(DEFAULT_TENANT_ID);
        task.setStatus(TaskStatus.PENDING.getCode());
        task.setPriority(priority);
        task.setDeleted(0);
        taskMapper.insert(task);
        insertStatusLog(task.getId(), null, task.getStatus(), userId, "创建任务");

        log.info("创建任务成功 taskId={}, projectId={}, operatorId={}", task.getId(), task.getProjectId(), userId);
        return taskConverter.toResponse(task);
    }

    @Override
    public List<TaskResponse> listTasks(TaskQueryRequest request) {
        Long userId = currentUserHolder.requireUserId();
        if (request.projectId() == null) {
            throw new BizException(ErrorCode.PARAM_INVALID, "项目 ID 不能为空");
        }
        projectService.requireAccessibleProject(request.projectId(), userId);
        LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<Task>()
                .eq(Task::getTenantId, DEFAULT_TENANT_ID)
                .eq(Task::getProjectId, request.projectId());
        if (request.status() != null && !request.status().isBlank()) {
            if (!TaskStatus.isValid(request.status())) {
                throw new BizException(ErrorCode.TASK_STATUS_VALUE_INVALID);
            }
            wrapper.eq(Task::getStatus, request.status());
        }
        if (request.assigneeId() != null) {
            wrapper.eq(Task::getAssigneeId, request.assigneeId());
        }
        if (request.keyword() != null && !request.keyword().isBlank()) {
            String keyword = request.keyword().trim();
            wrapper.and(condition -> condition.like(Task::getTitle, keyword).or().like(Task::getDescription, keyword));
        }
        wrapper.orderByDesc(Task::getUpdatedAt);
        return taskMapper.selectList(wrapper).stream()
                .map(taskConverter::toResponse)
                .toList();
    }

    @Override
    public TaskResponse getTaskDetail(Long id) {
        Long userId = currentUserHolder.requireUserId();
        return taskConverter.toResponse(requireAccessibleTask(id, userId));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public TaskResponse updateTask(Long id, UpdateTaskRequest request) {
        Long userId = currentUserHolder.requireUserId();
        Task task = requireAccessibleTask(id, userId);
        validateAssignee(request.assigneeId());
        if (!TaskPriority.isValid(request.priority())) {
            throw new BizException(ErrorCode.TASK_PRIORITY_INVALID);
        }
        taskConverter.updateEntity(task, request);
        taskMapper.updateById(task);
        log.info("修改任务基础信息 taskId={}, operatorId={}", id, userId);
        return taskConverter.toResponse(task);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public TaskResponse updateTaskStatus(Long id, UpdateTaskStatusRequest request) {
        Long userId = currentUserHolder.requireUserId();
        Task task = requireAccessibleTask(id, userId);
        if (!TaskStatus.isValid(request.status())) {
            throw new BizException(ErrorCode.TASK_STATUS_VALUE_INVALID);
        }
        String fromStatus = task.getStatus();
        if (request.status().equals(fromStatus)) {
            return taskConverter.toResponse(task);
        }
        task.setStatus(request.status());
        taskMapper.updateById(task);
        insertStatusLog(task.getId(), fromStatus, request.status(), userId, request.reason());
        log.info("任务状态变更 taskId={}, fromStatus={}, toStatus={}, operatorId={}", id, fromStatus, request.status(), userId);
        return taskConverter.toResponse(task);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteTask(Long id) {
        Long userId = currentUserHolder.requireUserId();
        requireAccessibleTask(id, userId);
        taskMapper.deleteById(id);
        log.info("逻辑删除任务 taskId={}, operatorId={}", id, userId);
    }

    private Task requireAccessibleTask(Long taskId, Long userId) {
        Task task = taskMapper.selectById(taskId);
        if (task == null || Integer.valueOf(1).equals(task.getDeleted())) {
            throw new BizException(ErrorCode.TASK_NOT_FOUND);
        }
        try {
            projectService.requireAccessibleProject(task.getProjectId(), userId);
        } catch (BizException exception) {
            throw new BizException(ErrorCode.TASK_NOT_FOUND);
        }
        return task;
    }

    private String normalizePriority(String priority) {
        if (priority == null || priority.isBlank()) {
            return TaskPriority.P2.getCode();
        }
        if (!TaskPriority.isValid(priority)) {
            throw new BizException(ErrorCode.TASK_PRIORITY_INVALID);
        }
        return priority;
    }

    private void validateAssignee(Long assigneeId) {
        if (assigneeId == null) {
            return;
        }
        User user = userMapper.selectById(assigneeId);
        if (user == null || Integer.valueOf(1).equals(user.getDeleted()) || !STATUS_ENABLED.equals(user.getStatus())) {
            throw new BizException(ErrorCode.USER_NOT_FOUND, "任务负责人不存在或不可用");
        }
    }

    private void insertStatusLog(Long taskId, String fromStatus, String toStatus, Long operatorId, String reason) {
        TaskStatusLog logEntity = new TaskStatusLog();
        logEntity.setTenantId(DEFAULT_TENANT_ID);
        logEntity.setTaskId(taskId);
        logEntity.setFromStatus(fromStatus);
        logEntity.setToStatus(toStatus);
        logEntity.setOperatorId(operatorId);
        logEntity.setSource(TaskStatusLogSource.MANUAL.getCode());
        logEntity.setReason(reason);
        logEntity.setTraceId(TraceContext.getTraceId());
        logEntity.setCreatedAt(LocalDateTime.now());
        taskStatusLogMapper.insert(logEntity);
    }
}
