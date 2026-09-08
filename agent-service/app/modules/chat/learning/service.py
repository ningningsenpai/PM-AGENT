"""按消息游标显式学习，并记录可追溯的纠正版本。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta

from app.core.errors import AppException
from app.core.identifiers import get_snowflake_id_generator
from app.llm.telemetry import capture_calls
from app.modules.chat.context.models import AgentContextEntry

from ..context.serialization import entry_data, utc_naive
from .prompts import LEARNING_PROMPT_VERSION, LEARNING_RULES
from .rules import candidate_status, normalized_key, resolve_entry, validate_source
from .schemas import LearningOutput


class LearningService:
    def __init__(
        self, repository, message_repository, conversations, contexts, runs, generator
    ):
        self.message_repo = message_repository
        self.repo, self.conversations, self.contexts, self.runs, self.generator = (
            repository,
            conversations,
            contexts,
            runs,
            generator,
        )

    async def learn(self, user_id, conversation_id, key, trace_id):
        conversation = await self.conversations.owned(user_id, conversation_id)
        project_id = conversation.project_id
        run, fresh = await self.runs.start(
            user_id, project_id, "learn", key, {}, trace_id, conversation_id
        )
        if not fresh:
            return self.runs.view(run)
        run_id, events = run.id, []
        try:
            pending = await self.message_repo.messages(
                conversation_id, after=conversation.learned_message_id
            )
            messages = [
                {"id": str(row.id), "content": row.content}
                for row in pending
                if row.role == "user"
            ]
            existing = [
                entry_data(row)
                for row in await self.repo.entries(user_id, project_id, effective=False)
            ]
            versions = {int(row["id"]): row["version"] for row in existing}
            await self.repo.session.commit()
            output = LearningOutput()
            if messages:
                prompt = (
                    LEARNING_RULES
                    + "\n"
                    + json.dumps(
                        {
                            "version": LEARNING_PROMPT_VERSION,
                            "now": datetime.now(UTC).replace(tzinfo=None).isoformat()
                            + "Z",
                            "messages": messages,
                            "existing": existing,
                        },
                        ensure_ascii=False,
                    )
                )
                with capture_calls(events):
                    output = await self.generator.generate(prompt, LearningOutput)
            changed = await self.apply(user_id, project_id, output, messages, versions)
            conversation = await self.message_repo.conversation(
                user_id, conversation_id, lock=True
            )
            if pending:
                conversation.learned_message_id = max(row.id for row in pending)
            result = {
                "changedEntries": changed,
                "processedMessages": len(messages),
                "learnedMessageId": str(conversation.learned_message_id),
                "promptVersion": LEARNING_PROMPT_VERSION,
            }
            await self.runs.finish(run_id, user_id, events, result)
        except asyncio.CancelledError:
            await self.runs.cancel(run_id, user_id, events)
            raise
        except Exception as exc:
            logging.getLogger(__name__).exception(
                "上下文业务运行失败，保留当前调用记录"
            )
            await self.repo.session.rollback()
            return await self.runs.finish(
                run_id,
                user_id,
                events,
                error=exc.message
                if isinstance(exc, AppException)
                else f"学习失败：{type(exc).__name__}",
            )
        result["snapshots"] = await self.contexts.publish(user_id, project_id)
        return await self.runs.finish(run_id, user_id, events, result)

    async def apply(self, user_id, project_id, output, messages, expected_versions):
        sources = {item["id"]: item["content"] for item in messages}
        scopes = {
            scope.scope_key: scope
            for scope in await self.contexts.scopes(user_id, project_id, lock=True)
        }
        existing = await self.repo.entries(user_id, project_id, effective=False)
        by_id = {row.id: row for row in existing}
        by_key = {(row.scope_key, row.kind, row.canonical_key): row for row in existing}
        changed, seen = [], set()
        for candidate in output.candidates:
            source = validate_source(candidate, sources)
            scope_id = None if candidate.scope == "user" else project_id
            scope_key = self.contexts.key(user_id, scope_id)
            canonical_key = normalized_key(candidate.key)
            row = resolve_entry(
                candidate,
                scope_key,
                canonical_key,
                by_id,
                by_key,
                seen,
                expected_versions,
            )
            status = candidate_status(candidate, source, row, by_key)
            before = entry_data(row) if row else {}
            if row is None:
                row = await self.repo.add(
                    AgentContextEntry(
                        id=get_snowflake_id_generator().next_id(),
                        user_id=user_id,
                        project_id=scope_id,
                        scope_key=scope_key,
                        kind=candidate.kind,
                        canonical_key=canonical_key,
                        content=candidate.content,
                        attributes={},
                        status=status,
                        version=1,
                    )
                )
                by_key[(scope_key, candidate.kind, canonical_key)] = row
            else:
                if (
                    row.content == candidate.content
                    and row.status == status
                    and not candidate.expires_at
                    and row.attributes.get("canonical") == candidate.canonical
                    and row.attributes.get("aliases", []) == candidate.aliases
                ):
                    continue
                row.version += 1
            seen.add(row.id)
            row.content = candidate.content
            row.status = status
            row.source_message_id = int(candidate.source_message_id)
            row.attributes = {
                "key": candidate.key,
                "aliases": candidate.aliases,
                "canonical": candidate.canonical,
                "sourceQuote": candidate.source_quote,
                "sourceType": "user_statement",
            }
            row.expires_at = utc_naive(candidate.expires_at)
            if row.kind == "short_memory" and row.expires_at is None:
                row.expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                    days=7
                )
            scopes[scope_key].version += 1
            await self.contexts.add_change(
                row, before, candidate.source_quote, row.source_message_id
            )
            changed.append(entry_data(row))
        return changed
