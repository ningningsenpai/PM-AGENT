package com.ning.pm.file.controller;

import cn.dev33.satoken.annotation.SaCheckLogin;
import com.ning.pm.common.response.R;
import com.ning.pm.file.dto.CreateProjectFileRequest;
import com.ning.pm.file.dto.FileReadUrlResponse;
import com.ning.pm.file.dto.OverwriteProjectFileRequest;
import com.ning.pm.file.dto.ProjectFileResponse;
import com.ning.pm.file.dto.UpdateProjectFilePathRequest;
import com.ning.pm.file.enums.FileBusinessType;
import com.ning.pm.file.service.ProjectFileService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * ProjectFileController 提供项目文件上传、覆盖、移动、读取和删除接口。
 *
 * @author ning
 * @date 2026-07-12
 */
@RestController
@RequestMapping("/api/v1/projects/{projectId}/files")
@Slf4j
@RequiredArgsConstructor
public class ProjectFileController {

    private final ProjectFileService projectFileService;

    /** 上传单个项目文件。 */
    @SaCheckLogin
    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public R<ProjectFileResponse> create(
            @PathVariable Long projectId,
            @RequestHeader("X-Idempotency-Key") String idempotencyKey,
            @Valid @ModelAttribute CreateProjectFileRequest request
    ) {
        log.info("开始上传项目文件 projectId={} business={} path={}",
                projectId, request.getBusinessCode(), request.getRelativePath());
        ProjectFileResponse response = projectFileService.createFile(projectId, idempotencyKey, request);
        log.info("项目文件上传成功 projectId={} fileId={} sizeBytes={}",
                projectId, response.id(), response.sizeBytes());
        return R.success(response);
    }

    /** 使用同一对象键覆盖文件内容。 */
    @SaCheckLogin
    @PutMapping(value = "/{fileId}/content", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public R<ProjectFileResponse> overwriteContent(
            @PathVariable Long projectId,
            @PathVariable Long fileId,
            @RequestHeader("X-Idempotency-Key") String idempotencyKey,
            @Valid @ModelAttribute OverwriteProjectFileRequest request
    ) {
        log.info("开始覆盖项目文件内容 projectId={} fileId={} lockVersion={}",
                projectId, fileId, request.getLockVersion());
        ProjectFileResponse response = projectFileService.overwriteContent(
                projectId, fileId, idempotencyKey, request
        );
        log.info("项目文件内容处理完成 projectId={} fileId={} status={}",
                projectId, fileId, response.status());
        return R.success(response);
    }

    /** 修改文件逻辑路径，不移动MinIO对象。 */
    @SaCheckLogin
    @PatchMapping("/{fileId}/path")
    public R<ProjectFileResponse> updatePath(
            @PathVariable Long projectId,
            @PathVariable Long fileId,
            @Valid @RequestBody UpdateProjectFilePathRequest request
    ) {
        log.info("开始修改项目文件路径 projectId={} fileId={} path={}",
                projectId, fileId, request.relativePath());
        ProjectFileResponse response = projectFileService.updatePath(projectId, fileId, request);
        log.info("项目文件路径修改成功 projectId={} fileId={} path={}",
                projectId, fileId, response.relativePath());
        return R.success(response);
    }

    /** 查询项目文件列表。 */
    @SaCheckLogin
    @GetMapping
    public R<List<ProjectFileResponse>> list(
            @PathVariable Long projectId,
            @RequestParam(required = false) FileBusinessType businessCode
    ) {
        log.info("开始查询项目文件 projectId={} business={}", projectId, businessCode);
        List<ProjectFileResponse> response = projectFileService.listFiles(projectId, businessCode);
        log.info("项目文件查询完成 projectId={} count={}", projectId, response.size());
        return R.success(response);
    }

    /** 生成五分钟有效的只读地址。 */
    @SaCheckLogin
    @GetMapping("/{fileId}/read-url")
    public R<FileReadUrlResponse> readUrl(
            @PathVariable Long projectId,
            @PathVariable Long fileId
    ) {
        log.info("开始生成文件只读地址 projectId={} fileId={}", projectId, fileId);
        FileReadUrlResponse response = projectFileService.createReadUrl(projectId, fileId);
        log.info("文件只读地址生成成功 projectId={} fileId={}", projectId, fileId);
        return R.success(response);
    }

    /** 删除文件记录及其唯一MinIO对象。 */
    @SaCheckLogin
    @DeleteMapping("/{fileId}")
    public R<Void> delete(
            @PathVariable Long projectId,
            @PathVariable Long fileId,
            @RequestParam Integer lockVersion
    ) {
        log.info("开始删除项目文件 projectId={} fileId={} lockVersion={}",
                projectId, fileId, lockVersion);
        projectFileService.deleteFile(projectId, fileId, lockVersion);
        log.info("项目文件删除成功 projectId={} fileId={}", projectId, fileId);
        return R.success(null);
    }
}
