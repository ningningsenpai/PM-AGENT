"""验证云端发布的原子入口、并发隔离和超时幂等恢复。"""

import asyncio
from unittest.mock import Mock

import pytest
from minio.error import S3Error

from app.core.errors import AppException
from app.infrastructure.storage import ObjectStorage, StorageLocation
from app.modules.chat.context.store import ContextStore, VersionCache
from tests.unit.chat.storage_stub import MemoryStorage


@pytest.fixture
def anyio_backend():
    return "asyncio"


def entry(content="中文简洁回答", project=None, kind="habit"):
    return {
        "id": "123",
        "projectId": str(project) if project else None,
        "kind": kind,
        "content": content,
        "attributes": {},
        "status": "active",
        "version": 1,
        "sourceMessageId": "100",
        "expiresAt": None,
    }


@pytest.mark.anyio
async def test_partial_files_never_publish_and_retry_recovers():
    storage = MemoryStorage()
    store = ContextStore(storage, "test", VersionCache())
    storage.fail_suffix = "short_memory.json"
    with pytest.raises(AppException):
        await store.publish(1, None, "", [entry()], "op-1", [])
    assert (await store.load(1, None)).version == 0
    storage.fail_suffix = None
    result = await store.publish(1, None, "", [entry()], "op-1", [])
    assert result.version == 1
    assert (await store.load(1, None)).entries[0]["content"] == "中文简洁回答"


@pytest.mark.anyio
async def test_racing_writers_and_stale_confirmation():
    store = ContextStore(MemoryStorage(), "test", VersionCache())
    results = await asyncio.gather(
        store.publish(1, None, "", [entry("甲")], "a", []),
        store.publish(1, None, "", [entry("乙")], "b", []),
        return_exceptions=True,
    )
    assert sum(isinstance(value, AppException) for value in results) == 1
    assert (await store.load(1, None)).version == 1
    with pytest.raises(AppException, match="版本"):
        await store.publish(1, None, "", [entry("丙")], "c", [])


@pytest.mark.anyio
async def test_lost_ack_and_old_operation_after_later_publication():
    storage = MemoryStorage()
    store = ContextStore(storage, "test", VersionCache())
    storage.lose_ack = True
    first = await store.publish(
        1, None, "", [entry("甲")], "first", [{"entryId": "123", "version": 1}]
    )
    second = await store.publish(1, None, first.revision, [entry("乙")], "second", [])
    recovered = await store.publish(
        1, None, "", [entry("甲")], "first", [{"entryId": "123", "version": 1}]
    )
    assert recovered.revision == first.revision
    assert (await store.load(1, None)).revision == second.revision
    assert (await store.history(1, None))[0]["version"] == 1
    with pytest.raises(AppException, match="不同内容"):
        await store.publish(1, None, "", [entry("恶意复用")], "first", [])


@pytest.mark.anyio
async def test_scope_and_cache_are_not_authority():
    storage = MemoryStorage()
    store = ContextStore(storage, "test", VersionCache())
    first = await store.publish(1, None, "", [entry()], "one", [])
    assert not (await store.load(2, None)).entries
    assert not (await store.load(1, 11)).entries
    await store.publish(1, None, first.revision, [entry("详细解释")], "two", [])
    assert (await store.load(1, None)).entries[0]["content"] == "详细解释"
    restarted = ContextStore(storage, "test", VersionCache())
    assert (await restarted.load(1, None)).version == 2
    with pytest.raises(AppException, match="其他范围"):
        await store.publish(1, 11, "", [entry(project=12)], "wrong", [])
    with pytest.raises(AppException, match="个人通用"):
        await store.publish(
            1,
            None,
            (await store.load(1, None)).revision,
            [entry(kind="project_rule")],
            "wrong-kind",
            [],
        )


def test_sdk_adapter_uses_conditional_headers_and_maps_conflict():
    client = Mock()
    storage = ObjectStorage(client, 60)
    location = StorageLocation("test", "context/manifest.json")
    storage.compare_and_put(location, b"{}", None)
    assert client._put_object.call_args.args[3]["If-None-Match"] == "*"
    storage.compare_and_put(location, b"{}", "abc")
    assert client._put_object.call_args.args[3]["If-Match"] == '"abc"'
    client._put_object.side_effect = S3Error(
        response=None,
        code="PreconditionFailed",
        message="失败",
        resource=None,
        request_id=None,
        host_id=None,
    )
    with pytest.raises(AppException, match="版本"):
        storage.compare_and_put(location, b"{}", "stale")
