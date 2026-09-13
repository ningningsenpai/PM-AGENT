"""待确认上下文草稿的查看、修订和精确版本发布。"""

from __future__ import annotations

import asyncio
import json
import logging

from app.core.errors import AppException, ErrorCode
from app.core.identifiers import get_snowflake_id_generator
from app.core.time import shanghai_now
from app.llm.telemetry import capture_calls
from app.project_context.file_detail.sensitive_content import sanitize_sensitive_content

from ..context.conflicts import normalized, validate_conflicts
from ..context.store import digest, json_bytes
from .candidates import build_entries, preview
from .prompts import LEARNING_PROMPT_VERSION, LEARNING_RULES, REFINEMENT_RULES
from .repository import LearningDraftRepository
from .schemas import LearningOutput
from .store import DraftStore


def new_id():
    return str(get_snowflake_id_generator().next_id())


class LearningService:
    def __init__(
        self,
        repository,
        message_repository,
        conversations,
        contexts,
        runs,
        generator,
        draft_repository=None,
    ):
        self.repo, self.message_repo, self.conversations = (
            repository,
            message_repository,
            conversations,
        )
        self.contexts, self.runs, self.generator = contexts, runs, generator
        self.drafts = DraftStore(
            draft_repository or LearningDraftRepository(repository.session)
        )

    @staticmethod
    def result(draft):
        return {
            "draftId": draft["id"],
            "draftVersion": draft["version"],
            "candidateCount": len(draft["candidates"]),
            "state": draft["state"],
            "promptVersion": LEARNING_PROMPT_VERSION,
        }

    async def failed(self, run_id, user_id, events, exc):
        logging.getLogger(__name__).exception("待确认上下文整理失败，已保留运行记录")
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
            "createdAt": shanghai_now().isoformat(),
            "learnedMessageId": str(learned_message_id),
            "base": {key: s.revision for key, s in snapshots.items()},
            "fileBase": {
                path: etag
                for snapshot in snapshots.values()
                for path, etag in snapshot.files.items()
            },
            "existing": [e for s in snapshots.values() for e in s.entries],
            "messages": messages,
            "candidates": self.materialize_candidates(output),
            "feedback": [],
            "history": [],
            "plan": None,
            "publications": {},
        }
        build_entries(draft, [c["id"] for c in draft["candidates"]])
        await self.drafts.save(draft, None)
        return draft

    @staticmethod
    def materialize_candidates(output):
        candidates, groups = [], {}
        for proposal in output.candidates:
            item = {
                "id": new_id(),
                "proposal": proposal.model_dump(
                    mode="json", by_alias=True, exclude={"coexist_group"}
                ),
            }
            candidates.append(item)
            if proposal.coexist_group:
                groups.setdefault(proposal.coexist_group, []).append(item)
        for group in groups.values():
            themes = {
                (
                    c["proposal"]["kind"],
                    c["proposal"]["scope"],
                    normalized(c["proposal"]["key"]),
                )
                for c in group
            }
            if (
                len(group) < 2
                or len(themes) != 1
                or any(
                    not c["proposal"]["conditions"]
                    or not (c["proposal"]["coexistReason"] or "").strip()
                    for c in group
                )
            ):
                raise AppException(
                    ErrorCode.PARAM_INVALID,
                    "拆分共存组须包含同主题的至少两条内容，并分别说明适用条件和共存理由",
                )
            for item in group:
                item["proposal"]["relatedEntryIds"] = list(
                    dict.fromkeys(
                        [
                            *item["proposal"]["relatedEntryIds"],
                            *(
                                other["proposal"]["replacesEntryId"] or other["id"]
                                for other in group
                                if other is not item
                            ),
                        ]
                    )
                )
        return candidates

    async def get(self, user_id, project_id, draft_id):
        await self.contexts.authorize(user_id, project_id)
        await self.repo.session.commit()
        draft, _ = await self.drafts.load(user_id, project_id, draft_id)
        await self.repo.session.commit()
        return preview(draft)

    async def list(self, user_id, project_id, conversation_id=None):
        await self.contexts.authorize(user_id, project_id)
        if conversation_id is not None:
            conversation = await self.conversations.owned(user_id, conversation_id)
            if conversation.project_id != project_id:
                raise AppException(ErrorCode.FORBIDDEN, "会话不属于当前项目")
        await self.repo.session.commit()
        drafts = await self.drafts.list(user_id, project_id, conversation_id)
        await self.repo.session.commit()
        return [preview(draft) for draft in drafts]

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
            await self.repo.session.commit()
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
                output = await self.generator.generate(
                    sanitize_sensitive_content(prompt).text, LearningOutput
                )
            # 替换范围由用户选择决定，模型不能删除其他候选。
            updated = self.drafts.next_version(prepared, "模型根据定向反馈重新整理")
            retained = [
                c
                for c in prepared["candidates"]
                if c["id"] not in request.candidate_ids
            ]
            replacements = self.materialize_candidates(output)
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
        await self.repo.session.commit()
        fingerprint = digest(json_bytes(request.model_dump(mode="json")))
        if draft.get("replacementDraftId"):
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT,
                "未发布内容已转入新的草稿，请在新草稿中确认",
            )
        if draft.get("plan") is None:
            self.drafts.editable(draft, request.version)
            current_files = await self.contexts.file_versions(user_id, project_id)
            selected_candidates = [
                candidate
                for candidate in draft["candidates"]
                if candidate["id"] in request.candidate_ids
            ]
            target_files = {
                candidate["proposal"]["targetFile"] for candidate in selected_candidates
            }
            if any(
                current_files.get(path) != draft.get("fileBase", {}).get(path)
                for path in target_files
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
            draft["state"] = "updating"
            await self.drafts.save(draft, etag)
            draft, etag = await self.drafts.load(user_id, project_id, draft_id)
            await self.repo.session.commit()
        elif draft["plan"]["requestHash"] != fingerprint:
            raise AppException(
                ErrorCode.RESOURCE_CONFLICT, "发布计划已经固定，只能恢复原确认请求"
            )
        plan = draft["plan"]
        target_files = sorted(
            {
                self.contexts.fixed.target_for(change["after"])
                for change in plan["changes"]
            }
        )
        for target_file in target_files:
            changed = [
                c
                for c in plan["changes"]
                if self.contexts.fixed.target_for(c["after"]) == target_file
            ]
            if draft["publications"].get(target_file, {}).get("published"):
                continue
            try:
                receipt = await self.contexts.fixed.apply(
                    user_id,
                    project_id,
                    target_file,
                    changed,
                    draft["fileBase"].get(target_file),
                )
                draft["publications"][target_file] = {
                    "published": True,
                    "version": receipt.version,
                    "revision": receipt.revision,
                    "error": None,
                }
            except AppException as exc:
                draft["publications"][target_file] = {
                    "published": False,
                    "error": exc.message,
                    "code": exc.error.code,
                }
        failures = any(not p["published"] for p in draft["publications"].values())
        draft["state"] = (
            "partial"
            if failures
            else "applied"
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
            if recovered["state"] == "applied":
                return recovered
            draft, etag = await self.drafts.load(user_id, project_id, draft_id)
            snapshots = await self.contexts.snapshots(user_id, project_id)
            candidates = [
                c
                for c in draft["candidates"]
                if c["id"] in draft["plan"]["candidateIds"]
                and not draft["publications"]
                .get(c["proposal"]["targetFile"], {})
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
            updated["fileBase"] = {
                path: etag
                for snapshot in snapshots.values()
                for path, etag in snapshot.files.items()
            }
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
        updated["fileBase"] = {
            path: etag
            for snapshot in snapshots.values()
            for path, etag in snapshot.files.items()
        }
        updated["existing"] = [entry for s in snapshots.values() for entry in s.entries]
        build_entries(updated, [c["id"] for c in updated["candidates"]])
        return preview(await self.drafts.save(updated, etag))
