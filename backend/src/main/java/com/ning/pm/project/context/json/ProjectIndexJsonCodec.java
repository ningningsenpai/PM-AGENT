package com.ning.pm.project.context.json;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.util.DefaultIndenter;
import com.fasterxml.jackson.core.util.DefaultPrettyPrinter;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.project.context.dto.ProjectIndex;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.time.LocalDateTime;
import java.util.List;

/** ProjectIndexJsonCodec 集中处理项目索引的 JSON 解析、补全与序列化。 */
@Component
@RequiredArgsConstructor
public class ProjectIndexJsonCodec {

    private final ObjectMapper objectMapper;

    public ObjectNode deserialize(byte[] content) {
        if (content == null || content.length == 0) {
            throw new SystemException(ErrorCode.PROJECT_INDEX_WRITE_FAILED, "项目上下文索引内容为空");
        }
        try {
            JsonNode index = objectMapper.readTree(content);
            if (index instanceof ObjectNode objectNode) {
                return objectNode;
            }
            throw new SystemException(ErrorCode.PROJECT_INDEX_WRITE_FAILED, "项目上下文索引格式不正确");
        } catch (IOException exception) {
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_WRITE_FAILED,
                    "项目上下文索引解析失败",
                    exception
            );
        }
    }

    public void complete(
            ObjectNode index,
            List<ProjectIndex.FileEntry> projectFiles,
            List<ProjectIndex.FileEntry> userFiles,
            long totalNodes,
            long failNodes
    ) {
        index.set("project", objectMapper.valueToTree(projectFiles));
        index.set("user", objectMapper.valueToTree(userFiles));
        index.put("updated_at", LocalDateTime.now().toString());

        ObjectNode summary = index.get("summary") instanceof ObjectNode currentSummary
                ? currentSummary
                : objectMapper.createObjectNode();
        summary.put("total_nodes", totalNodes);
        summary.put("active_files", projectFiles.size() + userFiles.size());
        summary.put("fail_nodes", failNodes);
        index.set("summary", summary);
    }

    public byte[] serialize(ProjectIndex index) {
        return serializeValue(index);
    }

    public byte[] serialize(ObjectNode index) {
        return serializeValue(index);
    }

    private byte[] serializeValue(Object value) {
        try {
            return objectMapper.writer(createPrettyPrinter()).writeValueAsBytes(value);
        } catch (JsonProcessingException exception) {
            throw new SystemException(
                    ErrorCode.PROJECT_INDEX_WRITE_FAILED,
                    "项目上下文索引序列化失败",
                    exception
            );
        }
    }

    private DefaultPrettyPrinter createPrettyPrinter() {
        DefaultIndenter indenter = new DefaultIndenter("  ", "\n");
        DefaultPrettyPrinter prettyPrinter = new DefaultPrettyPrinter();
        prettyPrinter.indentObjectsWith(indenter);
        prettyPrinter.indentArraysWith(indenter);
        return prettyPrinter;
    }
}
