package com.ning.pm.project.context.json;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.file.dto.parse.FileDetail;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

/** FileDetailJsonSerializer 负责将文件详情转换为可上传的 JSON 内容。 */
@Component
@RequiredArgsConstructor
public class FileDetailJsonSerializer {

    private final ObjectMapper objectMapper;

    public byte[] serialize(FileDetail detail) {
        try {
            return objectMapper.writerWithDefaultPrettyPrinter().writeValueAsBytes(detail);
        } catch (JsonProcessingException exception) {
            throw new SystemException(
                    ErrorCode.FILE_STORAGE_ERROR,
                    "文件详情序列化失败",
                    exception
            );
        }
    }
}
