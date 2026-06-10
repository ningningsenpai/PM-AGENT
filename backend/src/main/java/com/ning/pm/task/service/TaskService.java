package com.ning.pm.task.service;

import com.ning.pm.task.dto.CreateTaskRequest;
import com.ning.pm.task.dto.TaskQueryRequest;
import com.ning.pm.task.dto.TaskResponse;
import com.ning.pm.task.dto.UpdateTaskRequest;
import com.ning.pm.task.dto.UpdateTaskStatusRequest;

import java.util.List;

/**
 * TaskService 提供任务管理基础业务能力。
 *
 * @author ning
 * @date 2026-06-10
 */
public interface TaskService {

    TaskResponse createTask(CreateTaskRequest request);

    List<TaskResponse> listTasks(TaskQueryRequest request);

    TaskResponse getTaskDetail(Long id);

    TaskResponse updateTask(Long id, UpdateTaskRequest request);

    TaskResponse updateTaskStatus(Long id, UpdateTaskStatusRequest request);

    void deleteTask(Long id);
}
