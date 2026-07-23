package com.ning.pm.file.service.validation;

import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.dto.parse.FileAnalysisRequest;
import com.ning.pm.file.dto.parse.FileAnalysisResult;
import com.ning.pm.file.dto.parse.FileDetail;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** FileAnalysisResultValidator 统一校验 Python 文件分析接口的批量返回结果。 */
@Component
public class FileAnalysisResultValidator {

    private static final String ANALYSIS_SUCCESS = "success";
    private static final String ANALYSIS_FAILED = "failed";

    public void validate(
            Long projectId,
            List<FileAnalysisRequest> requests,
            List<FileAnalysisResult> results
    ) {
        if (results == null) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析接口未返回结果");
        }
        if (results.size() != requests.size()) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析结果数量与请求数量不一致");
        }

        Map<Long, FileAnalysisRequest> requestByFileId = new HashMap<>();
        for (FileAnalysisRequest request : requests) {
            requestByFileId.put(request.fileId(), request);
        }

        Set<Long> resultFileIds = new HashSet<>();
        for (FileAnalysisResult result : results) {
            validateResult(projectId, requestByFileId, resultFileIds, result);
        }
    }

    public boolean isSuccessful(FileAnalysisResult result) {
        return ANALYSIS_SUCCESS.equals(result.status());
    }

    private void validateResult(
            Long projectId,
            Map<Long, FileAnalysisRequest> requestByFileId,
            Set<Long> resultFileIds,
            FileAnalysisResult result
    ) {
        if (result == null || result.fileId() == null || !resultFileIds.add(result.fileId())) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析结果包含空值或重复文件");
        }

        FileAnalysisRequest request = requestByFileId.get(result.fileId());
        if (request == null
                || !projectId.equals(result.projectId())
                || sameText(request.contentHash(), result.contentHash())
                || sameText(request.analysisVersion(), result.analysisVersion())) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析结果与原始请求不一致");
        }

        if (isSuccessful(result)) {
            validateSuccessfulResult(request, result.detail());
        } else if (!ANALYSIS_FAILED.equals(result.status()) || result.detail() != null) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 文件分析结果状态不合法");
        }
    }

    private void validateSuccessfulResult(FileAnalysisRequest request, FileDetail detail) {
        if (detail == null
                || !request.projectId().equals(detail.projectId())
                || !request.fileId().equals(detail.fileId())
                || sameText(request.storageUuid(), detail.storageUuid())
                || sameText(request.storageName(), detail.storageName())
                || sameText(request.detailRef(), detail.detailRef())
                || sameText(request.originalPath(), detail.originalPath())
                || sameText(request.minioPath(), detail.minioPath())
                || !request.sizeBytes().equals(detail.sizeBytes())
                || sameText(request.contentType(), detail.contentType())
                || sameText(request.contentHash(), detail.contentHash())
                || sameText(request.analysisVersion(), detail.analysisVersion())) {
            throw new SystemException(ErrorCode.SYSTEM_ERROR, "Python 返回的文件详情身份字段不一致");
        }
    }

    private boolean sameText(String left, String right) {
        return left == null ? right != null : !left.equals(right);
    }
}
