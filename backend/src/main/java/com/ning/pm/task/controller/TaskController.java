package com.ning.pm.task.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.response.R;
import com.ning.pm.task.dto.CreateTaskRequest;
import com.ning.pm.task.dto.TaskQueryRequest;
import com.ning.pm.task.dto.TaskResponse;
import com.ning.pm.task.dto.UpdateTaskRequest;
import com.ning.pm.task.dto.UpdateTaskStatusRequest;
import com.ning.pm.task.service.TaskService;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * TaskController 提供第 1 阶段任务管理接口。
 *
 * @author ning
 * @date 2026-06-10
 */
@RestController
@RequestMapping("/api/v1/tasks")
public class TaskController {

    private final TaskService taskService;

    public TaskController(TaskService taskService) {
        this.taskService = taskService;
    }

    /** 创建任务。 */
    @SaCheckLogin
    @PostMapping
    public R<TaskResponse> createTask(@Valid @RequestBody CreateTaskRequest request) {
        return R.success(taskService.createTask(request));
    }

    /** 查询项目任务列表。 */
    @SaCheckLogin
    @GetMapping
    public R<List<TaskResponse>> listTasks(@RequestParam Long projectId,
                                           @RequestParam(required = false) String status,
                                           @RequestParam(required = false) Long assigneeId,
                                           @RequestParam(required = false) String keyword) {
        return R.success(taskService.listTasks(new TaskQueryRequest(projectId, status, assigneeId, keyword)));
    }

    /** 查询任务详情。 */
    @SaCheckLogin
    @GetMapping("/{id}")
    public R<TaskResponse> getTaskDetail(@PathVariable Long id) {
        return R.success(taskService.getTaskDetail(id));
    }

    /** 修改任务基础信息。 */
    @SaCheckLogin
    @PutMapping("/{id}")
    public R<TaskResponse> updateTask(@PathVariable Long id, @Valid @RequestBody UpdateTaskRequest request) {
        return R.success(taskService.updateTask(id, request));
    }

    /** 修改任务状态。 */
    @SaCheckLogin
    @PutMapping("/{id}/status")
    public R<TaskResponse> updateTaskStatus(@PathVariable Long id,
                                            @Valid @RequestBody UpdateTaskStatusRequest request) {
        return R.success(taskService.updateTaskStatus(id, request));
    }

    /** 逻辑删除任务。 */
    @SaCheckLogin
    @DeleteMapping("/{id}")
    public R<Void> deleteTask(@PathVariable Long id) {
        taskService.deleteTask(id);
        return R.success(null);
    }
}
