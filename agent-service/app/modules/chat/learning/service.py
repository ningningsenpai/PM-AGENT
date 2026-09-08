"""显式学习：生成云端草稿、定向反馈和精确版本确认发布。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from app.core.errors import AppException, ErrorCode
from app.core.identifiers import get_snowflake_id_generator
from app.llm.telemetry import capture_calls
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content

from ..context.conflicts import normalized, validate_conflicts
from ..context.store import digest, json_bytes
from .candidates import build_entries, preview
from .prompts import LEARNING_PROMPT_VERSION, LEARNING_RULES, REFINEMENT_RULES
from .schemas import LearningOutput
from .store import DraftStore


def new_id():
    return str(get_snowflake_id_generator().next_id())


class LearningService:
    def __init__(
        self, repository, message_repository, conversations, contexts, runs, generator
    ):
        self.repo, self.message_repo, self.conversations = (
            repository,
            message_repository,
            conversations,
        )
        self.contexts, self.runs, self.generator = contexts, runs, generator
        self.drafts = DraftStore(contexts.store)

    async def learn(self, user_id, conversation_id, key, trace_id):
        conversation = await self.conversations.owned(user_id, conversation_id)
        project_id, cursor = conversation.project_id, conversation.learned_message_id
        await self.repo.session.commit()
        previous_drafts = await self.drafts.list(user_id, project_id, conversation_id)
        cursor = max(
            [cursor, *[int(d.get("learnedMessageId", "0")) for d in previous_drafts]]
        )
        run, fresh = await self.runs.start(
            user_id, project_id, "learn", key, {}, trace_id, conversation_id
        )
        run_id, events = run.id, []
        if not fresh:
            recovered = next(
                (d for d in previous_drafts if d["id"] == str(run_id)), None
            )
            if recovered and run.status != "success":
                conversation = await self.message_repo.conversation(
                    user_id, conversation_id, lock=True
                )
                conversation.learned_message_id = max(
                    conversation.learned_message_id,
                    int(recovered.get("learnedMessageId", "0")),
                )
                return await self.runs.finish(
                    run_id,
                    user_id,
                    run.events,
                    self.result(recovered, len(recovered["messages"])),
                )
            return self.runs.view(run)
        try:
            pending = await self.message_repo.messages(conversation_id, after=cursor)
            next_cursor = max((row.id for row in pending), default=cursor)
            messages = [
                {
                    "id": str(row.id),
                    "content": sanitize_sensitive_content(row.content).text,
                }
                for row in pending
                if row.role == "user"
            ]
            snapshots = await self.contexts.snapshots(user_id, project_id)
            existing = [
                entry for snapshot in snapshots.values() for entry in snapshot.entries
            ]
            output = LearningOutput()
            if messages:
                prompt = (
                    LEARNING_RULES
                    + "\n"
                    + json.dumps(
                        {
                            "messages": messages,
                            "existing": existing,
                            "now": datetime.now(UTC).isoformat(),
                        },
                        ensure_ascii=False,
                    )
                )
                with capture_calls(events):
                    output = await self.generator.generate(prompt, LearningOutput)
            draft = await self.create_draft(
                user_id,
                project_id,
                conversation_id,
                str(run_id),
                output,
                messages,
                snapshots,
                learned_message_id=next_cursor,
            )
            # 草稿先落云端；游标只表示已完成提取，不表示用户已经确认。
            conversation = await self.message_repo.conversation(
                user_id, conversation_id, lock=True
            )
            conversation.learned_message_id = max(
                conversation.learned_message_id, next_cursor
            )
            return await self.runs.finish(
                run_id, user_id, events, self.result(draft, len(messages))
            )
        except asyncio.CancelledError:
            await self.runs.cancel(run_id, user_id, events)
            raise
        except Exception as exc:
            return await self.failed(run_id, user_id, events, exc)

    @staticmethod
    def result(draft, processed=None):
        result = {
            "draftId": draft["id"],
            "draftVersion": draft["version"],
            "candidateCount": len(draft["candidates"]),
            "state": draft["state"],
            "promptVersion": LEARNING_PROMPT_VERSION,
        }
        if processed is not None:
            result["processedMessages"] = processed
        return result

    async def failed(self, run_id, user_id, events, exc):
        logging.getLogger(__name__).exception("显式学习操作失败，已保留运行记录")
        await self.repo.session.rollback()
        return await self.runs.finish(
            run_id,
            user_id,
            events,
            error=exc.message
            if isinstance(exc, AppException)
            else f"学习操作失败：{type(exc).__name__}",
        )

    async def create_draft(
        self,
        user_id,
        project_id,
        conversation_id,
        draft_id,
        output,
        messages,
        snapshots=None,
        *,
        learned_message_id=0,
    ):
        snapshots = snapshots or await self.contexts.snapshots(user_id, project_id)
        draft = {
            "id": str(draft_id),
            "userId": str(user_id),
            "projectId": str(project_id),
            "conversationId": str(conversation_id),
            "version": 1,
            "state": "pending",
            "createdAt": datetime.now(UTC).isoformat(),
            "learnedMessageId": str(learned_message_id),
            "base": {key: s.revision for key, s in snapshots.items()},
            "existing": [e for s in snapshots.values() for e in s.entries],
            "messages": messages,
            "candidates": [
                {"id": new_id(), "proposal": c.model_dump(mode="json", by_alias=True)}
                for c in output.candidates
            ],
            "feedback": [],
            "history": [],
            "plan": None,
            "publications": {},
        }
        build_entries(draft, [c["id"] for c in draft["candidates"]])
        await self.drafts.save(draft, None)
        return draft

    async def get(self, user_id, project_id, draft_id):
        await self.contexts.authorize(user_id, project_id)
        await self.repo.session.commit()
        draft, _ = await self.drafts.load(user_id, project_id, draft_id)
        return preview(draft)

    async def list(self, user_id, project_id, conversation_id=None):
        await self.contexts.authorize(user_id, project_id)
        if conversation_id is not None:
            conversation = await self.conversations.owned(user_id, conversation_id)
            if conversation.project_id != project_id:
                raise AppException(ErrorCode.FORBIDDEN, "会话不属于当前项目")
        await self.repo.session.commit()
        return [
            preview(d)
            for d in await self.drafts.list(user_id, project_id, conversation_id)
        ]

    async def edit(self, user_id, project_id, draft_id, request):
        await self.get(user_id, project_id, draft_id)
        draft, etag = await self.drafts.load(user_id, project_id, draft_id)
        self.drafts.editable(draft, request.version)
        ids = {c["id"] for c in draft["candidates"]}
        if (
            len({c.id for c in request.candidates}) != len(request.candidates)
            or not {c.id for c in request.candidates} <= ids
        ):
            raise AppException(ErrorCode.PARAM_INVALID, "人工修改包含未知或重复候选")
        updated = self.drafts.next_version(draft, request.reason)
        updated["candidates"] = [
            c.model_dump(mode="json", by_alias=True) for c in request.candidates
        ]
        build_entries(updated, [c["id"] for c in updated["candidates"]])
        return preview(await self.drafts.save(updated, etag))

    async def refine(self, user_id, project_id, draft_id, request, key, trace_id):
        draft = await self.get(user_id, project_id, draft_id)
        run, fresh = await self.runs.start(
            user_id,
            project_id,
            "learn_refine",
            key,
            {"draftId": str(draft_id), **request.model_dump(mode="json")},
            trace_id,
            int(draft["conversationId"]),
        )
        if not fresh:
            return self.runs.view(run)
        run_id, events = run.id, []
        try:
            draft, etag = await self.drafts.load(user_id, project_id, draft_id)
            self.drafts.editable(draft, request.version)
            selected = [
                c for c in draft["candidates"] if c["id"] in request.candidate_ids
            ]
            if len(selected) != len(set(request.candidate_ids)):
                raise AppException(ErrorCode.PARAM_INVALID, "反馈目标不属于当前草稿")
            feedback = {
                "id": new_id(),
                "text": sanitize_sensitive_content(request.feedback).text,
                "candidateIds": request.candidate_ids,
            }
            # 先保存用户反馈，模型失败后仍可查看；重试不会丢失原解释。
            prepared = self.drafts.next_version(draft, "用户提交定向反馈")
            prepared["feedback"].append(feedback)
            await self.drafts.save(prepared, etag)
            persisted, etag = await self.drafts.load(user_id, project_id, draft_id)
            if persisted != prepared:
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT,
                    "反馈提交后草稿已被其他操作修改，请重新选择",
                )
            source_ids = {c["proposal"]["sourceMessageId"] for c in selected} | {
                feedback["id"]
            }
            selected_sources = {}
            for item in selected:
                proposal = item["proposal"]
                selected_sources.setdefault(proposal["sourceMessageId"], []).append(
                    proposal["sourceQuote"]
                )
            prompt = (
                REFINEMENT_RULES
                + "\n"
                + LEARNING_RULES
                + "\n"
                + json.dumps(
                    {
                        "selected": selected,
                        "messages": [
                            {"id": source_id, "content": "；".join(quotes)}
                            for source_id, quotes in selected_sources.items()
                        ],
                        "feedback": [
                            f for f in prepared["feedback"] if f["id"] in source_ids
                        ],
                        "existing": prepared["existing"],
                    },
                    ensure_ascii=False,
                )
            )
            with capture_calls(events):
                output = await self.generator.generate(prompt, LearningOutput)
            # 替换范围由用户选择决定，模型不能删除其他候选。
            updated = self.drafts.next_version(prepared, "模型根据定向反馈重新整理")
            retained = [
                c
                for c in prepared["candidates"]
                if c["id"] not in request.candidate_ids
            ]
            replacements = [
                {"id": new_id(), "proposal": c.model_dump(mode="json", by_alias=True)}
                for c in output.candidates
            ]
            if len(retained) + len(replacements) > 30:
                raise AppException(
                    ErrorCode.PARAM_INVALID, "整理后的候选超过三十条，请缩小范围"
                )
            allowed_targets = {c["proposal"].get("replacesEntryId") for c in selected}
            related_targets = {
                entry_id
                for c in selected
                for entry_id in c["proposal"].get("relatedEntryIds", [])
            }
            for c in output.candidates:
                if c.source_message_id not in source_ids:
                    raise AppException(
                        ErrorCode.FORBIDDEN, "反馈整理引用了未选中内容的来源"
                    )
                if c.source_message_id != feedback["id"] and not any(
                    c.source_quote in quote
                    for quote in selected_sources.get(c.source_message_id, [])
                ):
                    raise AppException(ErrorCode.FORBIDDEN, "反馈整理超出所选原文范围")
                if normalized(c.key) not in {
                    normalized(item["proposal"]["key"]) for item in selected
                }:
                    raise AppException(
                        ErrorCode.PARAM_INVALID,
                        "定向整理须保留所选主题，新主题请另行学习或人工编辑",
                    )
                if (
                    c.replaces_entry_id
                    and c.replaces_entry_id not in allowed_targets | related_targets
                ):
                    raise AppException(
                        ErrorCode.FORBIDDEN,
                        "反馈整理不能改写未选中候选关联范围之外的条目",
                    )
            updated["candidates"] = retained + replacements
            build_entries(updated, [c["id"] for c in updated["candidates"]])
            await self.drafts.save(updated, etag)
            return await self.runs.finish(run_id, user_id, events, self.result(updated))
        except asyncio.CancelledError:
            await self.runs.cancel(run_id, user_id, events)
            raise
        except Exception as exc:
            return await self.failed(run_id, user_id, events, exc)

    async def confirm(self, user_id, project_id, draft_id, request):
        await self.get(user_id, project_id, draft_id)
        draft, etag = await self.drafts.load(user_id, project_id, draft_id)
        fingerprint = digest(json_bytes(request.model_dump(mode="json")))
        if draft.get("replacementDraftId"):
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT,
                "未发布内容已转入新的草稿，请在新草稿中确认",
            )
        if draft.get("plan") is None:
            self.drafts.editable(draft, request.version)
            snapshots = await self.contexts.snapshots(user_id, project_id)
            if any(
                s.revision != draft["base"][scope] for scope, s in snapshots.items()
            ):
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT,
                    "正式内容已更新，请刷新草稿基础版本并重新确认差异",
                )
            entries, changes = build_entries(draft, request.candidate_ids)
            validate_conflicts(entries, {c["entryId"] for c in changes})
            draft["plan"] = {
                "requestHash": fingerprint,
                "entries": entries,
                "changes": changes,
                "candidateIds": request.candidate_ids,
                "version": request.version,
            }
            draft["state"] = "publishing"
            await self.drafts.save(draft, etag)
            draft, etag = await self.drafts.load(user_id, project_id, draft_id)
        elif draft["plan"]["requestHash"] != fingerprint:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "发布计划已经固定，只能恢复原确认请求"
            )
        plan = draft["plan"]
        for pid in (None, project_id):
            scope = self.contexts.key(user_id, pid)
            changed = [
                c
                for c in plan["changes"]
                if c["after"]["projectId"] == (str(pid) if pid else None)
            ]
            if not changed or draft["publications"].get(scope, {}).get("published"):
                continue
            try:
                receipt = await self.contexts.store.publish(
                    user_id,
                    pid,
                    draft["base"][scope],
                    [
                        e
                        for e in plan["entries"]
                        if e["projectId"] == (str(pid) if pid else None)
                    ],
                    f"draft:{draft_id}:v{plan['version']}:{scope}",
                    changed,
                )
                draft["publications"][scope] = {
                    "published": True,
                    "version": receipt.version,
                    "revision": receipt.revision,
                    "error": None,
                }
            except AppException as exc:
                draft["publications"][scope] = {
                    "published": False,
                    "error": exc.message,
                    "code": exc.error.code,
                }
        failures = any(not p["published"] for p in draft["publications"].values())
        draft["state"] = (
            "partial"
            if failures
            else "published"
            if plan["candidateIds"]
            else "discarded"
        )
        await self.drafts.save(draft, etag)
        return preview(draft)

    async def rebase(self, user_id, project_id, draft_id, version):
        await self.get(user_id, project_id, draft_id)
        draft, etag = await self.drafts.load(user_id, project_id, draft_id)
        if draft.get("replacementDraftId"):
            return await self.get(user_id, project_id, draft["replacementDraftId"])
        if draft.get("plan") is not None:
            if draft["version"] != version or draft["state"] != "partial":
                raise AppException(
                    ErrorCode.RESOURCE_CONFLICT,
                    "仅部分发布失败的草稿可以重新整理未发布范围",
                )
            # 先恢复未知发布结果，再创建剩余范围的草稿，避免成功内容重复应用。
            from .schemas import ConfirmDraft

            recovered = await self.confirm(
                user_id,
                project_id,
                draft_id,
                ConfirmDraft(
                    version=draft["plan"]["version"],
                    candidate_ids=draft["plan"]["candidateIds"],
                ),
            )
            if recovered["state"] == "published":
                return recovered
            draft, etag = await self.drafts.load(user_id, project_id, draft_id)
            snapshots = await self.contexts.snapshots(user_id, project_id)
            candidates = [
                c
                for c in draft["candidates"]
                if c["id"] in draft["plan"]["candidateIds"]
                and not draft["publications"]
                .get(
                    self.contexts.key(
                        user_id,
                        None if c["proposal"]["scope"] == "user" else project_id,
                    ),
                    {},
                )
                .get("published")
            ]
            import copy

            updated = copy.deepcopy(draft)
            updated.update(
                id=new_id(),
                version=1,
                state="pending",
                plan=None,
                publications={},
                candidates=candidates,
                parentDraftId=draft["id"],
            )
            updated["base"] = {key: s.revision for key, s in snapshots.items()}
            updated["existing"] = [
                entry for s in snapshots.values() for entry in s.entries
            ]
            build_entries(updated, [c["id"] for c in candidates])
            await self.drafts.save(updated, None)
            draft["replacementDraftId"] = updated["id"]
            await self.drafts.save(draft, etag)
            return preview(updated)
        self.drafts.editable(draft, version)
        snapshots = await self.contexts.snapshots(user_id, project_id)
        updated = self.drafts.next_version(draft, "重新读取正式内容，等待用户再次核对")
        updated["base"] = {key: s.revision for key, s in snapshots.items()}
        updated["existing"] = [entry for s in snapshots.values() for entry in s.entries]
        build_entries(updated, [c["id"] for c in updated["candidates"]])
        return preview(await self.drafts.save(updated, etag))
