package com.ning.pm.project.context;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.domain.ProjectFile;
import com.ning.pm.file.repository.ProjectFileMapper;
import com.ning.pm.infrastructure.storage.ObjectStorageService;
import com.ning.pm.project.context.dto.ProjectIndex;
import com.ning.pm.project.domain.Project;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.ReentrantLock;

/**
 * ProjectIndexService 以项目级进程内互斥编排索引初始化、重建和补偿删除。
 *
 * @author ning
 * @date 2026-07-15
 */
@Service
@RequiredArgsConstructor
public class ProjectIndexService {

    private static final int MAX_ATTEMPTS = 3;

    private final ProjectFileMapper fileMapper;
    private final ProjectIndexFactory indexFactory;
    private final ProjectIndexWriter indexWriter;
    private final ObjectStorageService objectStorageService;
    private final ConcurrentHashMap<Long, ReentrantLock> projectLocks = new ConcurrentHashMap<>();

    public void initialize(Project project) {
        ProjectIndex index = indexFactory.createInitialIndex(project);
        // MAP 定义的 projectId -> ReentrantLock 映射锁
        ReentrantLock lock = projectLock(project.getId());
        lock.lock();
        try {
            RuntimeException lastException = null;
            for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
                try {
                    indexWriter.writeIndex(project.getOwnerUserId(), project.getId(), index);
                    return;
                } catch (RuntimeException exception) {
                    lastException = exception;
                }
            }
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_INIT_FAILED,
                    "项目上下文索引连续三次上传失败",
                    lastException
            );
        } finally {
            lock.unlock();
        }
    }

    public void rebuild(Project project) {
        rebuildInternal(project, null);
    }

    public void rebuild(Project project, ProjectScanSummary scanSummary) {
        rebuildInternal(project, scanSummary);
    }

    private void rebuildInternal(Project project, ProjectScanSummary scanSummary) {
        ReentrantLock lock = projectLock(project.getId());
        lock.lock();
        try {
            List<ProjectFile> files = fileMapper.selectList(new LambdaQueryWrapper<ProjectFile>()
                    .eq(ProjectFile::getProjectId, project.getId())
                    .orderByAsc(ProjectFile::getBusinessCode)
                    .orderByAsc(ProjectFile::getRelativePath));
            ProjectIndex index = indexFactory.buildCurrentIndex(
                    project,
                    scanSummary == null
                            ? ProjectScanSummary.fromStoredFiles(files.size())
                            : scanSummary,
                    files
            );
            try {
                indexWriter.writeIndex(project.getOwnerUserId(), project.getId(), index);
            } catch (RuntimeException exception) {
                throw new SystemException(
                        ErrorCode.PROJECT_INDEX_WRITE_FAILED,
                        "项目上下文索引整体写入失败",
                        exception
                );
            }
        } finally {
            lock.unlock();
        }
    }

    public void removeInitialIndexWithRetry(Project project) {
        RuntimeException lastException = null;
        for (int attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
            try {
                objectStorageService.removeObject(indexWriter.indexLocation(
                        project.getOwnerUserId(),
                        project.getId()
                ));
                return;
            } catch (RuntimeException exception) {
                lastException = exception;
            }
        }
        if (lastException != null) {
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_INIT_FAILED,
                    "回滚项目时清理初始索引失败",
                    lastException
            );
        }
    }

    private ReentrantLock projectLock(Long projectId) {
        return projectLocks.computeIfAbsent(projectId, ignored -> new ReentrantLock());
    }
}
