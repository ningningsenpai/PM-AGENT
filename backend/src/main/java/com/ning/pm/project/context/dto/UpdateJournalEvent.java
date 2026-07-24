package com.ning.pm.project.context.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

/**
 * UpdateJournalEvent 表示 system/update_journal.jsonl 中的一行更新事件。
 *
 * @author ning
 * @date 2026-07-24
 */
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record UpdateJournalEvent(
        String eventId,
        Long projectId,
        String eventType,
        String target,
        String source,
        String summary,
        String createdAt
) {
}
