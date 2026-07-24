package com.ning.pm.project.context.json;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.util.DefaultIndenter;
import com.fasterxml.jackson.core.util.DefaultPrettyPrinter;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ning.pm.common.errorcode.ErrorCode;
import com.ning.pm.common.exception.SystemException;
import com.ning.pm.project.context.dto.LongTermMemory;
import com.ning.pm.project.context.dto.ProjectSpecification;
import com.ning.pm.project.context.dto.ShortTermMemory;
import com.ning.pm.project.context.dto.UpdateJournalEvent;
import com.ning.pm.project.context.dto.UserHabits;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * ProjectContextJsonSerializer 负责将项目上下文对象转换为 JSON 或 JSONL 内容。
 *
 * @author ning
 * @date 2026-07-24
 */
@Component
@RequiredArgsConstructor
public class ProjectContextJsonSerializer {

    private final ObjectMapper objectMapper;

    public byte[] serialize(ProjectSpecification specification) {
        return serializeJson(specification);
    }

    public byte[] serialize(LongTermMemory memory) {
        return serializeJson(memory);
    }

    public byte[] serialize(ShortTermMemory memory) {
        return serializeJson(memory);
    }

    public byte[] serialize(UserHabits habits) {
        return serializeJson(habits);
    }

    public byte[] serializeJournal(List<UpdateJournalEvent> events) {
        if (events == null) {
            throw serializationException("更新日志事件不能为空", null);
        }
        if (events.isEmpty()) {
            return new byte[0];
        }
        try {
            StringBuilder content = new StringBuilder();
            for (UpdateJournalEvent event : events) {
                content.append(objectMapper.writeValueAsString(event)).append('\n');
            }
            return content.toString().getBytes(StandardCharsets.UTF_8);
        } catch (JsonProcessingException exception) {
            throw serializationException("项目上下文更新日志序列化失败", exception);
        }
    }

    private byte[] serializeJson(Object value) {
        if (value == null) {
            throw serializationException("项目上下文对象不能为空", null);
        }
        try {
            return objectMapper.writer(createPrettyPrinter()).writeValueAsBytes(value);
        } catch (JsonProcessingException exception) {
            throw serializationException("项目上下文 JSON 序列化失败", exception);
        }
    }

    private DefaultPrettyPrinter createPrettyPrinter() {
        DefaultIndenter indenter = new DefaultIndenter("  ", "\n");
        DefaultPrettyPrinter prettyPrinter = new DefaultPrettyPrinter();
        prettyPrinter.indentObjectsWith(indenter);
        prettyPrinter.indentArraysWith(indenter);
        return prettyPrinter;
    }

    private SystemException serializationException(String message, Throwable cause) {
        return cause == null
                ? new SystemException(ErrorCode.FILE_STORAGE_ERROR, message)
                : new SystemException(ErrorCode.FILE_STORAGE_ERROR, message, cause);
    }
}
