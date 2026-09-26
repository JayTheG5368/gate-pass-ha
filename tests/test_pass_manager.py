"""Tests for the Gate Pass pass manager."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from custom_components.gate_pass.pass_manager import (
    PassBusyError,
    PassManager,
    PassUnavailableError,
)


class MemoryStorage:
    """Minimal in-memory storage adapter."""

    def __init__(self) -> None:
        self.data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any] | None:
        return self.data

    async def async_save(self, data: dict[str, Any]) -> None:
        self.data = data


@pytest.mark.asyncio
async def test_create_stores_only_hash_and_returns_secret_once() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()

    guest_pass, secret = await manager.async_create(
        label="Paketdienst", duration_hours=1, max_uses=1
    )

    assert secret
    assert "secret" not in guest_pass
    assert "secret_hash" not in guest_pass
    assert storage.data is not None
    stored = storage.data["passes"][0]
    assert stored["secret_hash"]
    assert secret not in str(stored)


@pytest.mark.asyncio
async def test_successful_use_is_committed_and_exhausts_one_use_pass() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()
    guest_pass, secret = await manager.async_create(
        label="Gast", duration_hours=1, max_uses=1
    )

    await manager.async_reserve_use(guest_pass["pass_id"], secret)
    with pytest.raises(PassBusyError):
        await manager.async_reserve_use(guest_pass["pass_id"], secret)

    committed = await manager.async_commit_use(guest_pass["pass_id"])
    assert committed["use_count"] == 1
    assert committed["active"] is False
    with pytest.raises(PassUnavailableError):
        await manager.async_get_valid(guest_pass["pass_id"], secret)


@pytest.mark.asyncio
async def test_failed_action_release_does_not_consume_pass() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()
    guest_pass, secret = await manager.async_create(
        label="Gast", duration_hours=1, max_uses=1
    )

    await manager.async_reserve_use(guest_pass["pass_id"], secret)
    await manager.async_release_use(guest_pass["pass_id"])

    valid = await manager.async_get_valid(guest_pass["pass_id"], secret)
    assert valid["use_count"] == 0
    assert valid["active"] is True


@pytest.mark.asyncio
async def test_expired_pass_is_rejected() -> None:
    current = [datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)]
    storage = MemoryStorage()
    manager = PassManager(storage, now=lambda: current[0])
    await manager.async_load()
    guest_pass, secret = await manager.async_create(
        label="Gast", duration_hours=0.5, max_uses=0
    )

    current[0] += timedelta(hours=1)

    with pytest.raises(PassUnavailableError, match="expired"):
        await manager.async_get_valid(guest_pass["pass_id"], secret)
    assert storage.data["passes"][0]["active"] is False
    assert await manager.async_list_active() == []


@pytest.mark.asyncio
async def test_scheduled_pass_is_blocked_until_start_and_expires_after_duration() -> (
    None
):
    current = [datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)]
    valid_from = current[0] + timedelta(hours=4)
    storage = MemoryStorage()
    manager = PassManager(storage, now=lambda: current[0])
    await manager.async_load()

    guest_pass, secret = await manager.async_create(
        label="Morgen",
        duration_hours=2,
        max_uses=1,
        valid_from=valid_from,
    )

    assert datetime.fromisoformat(guest_pass["valid_from"]) == valid_from
    assert datetime.fromisoformat(guest_pass["expires_at"]) == valid_from + timedelta(
        hours=2
    )
    assert len(await manager.async_list_active()) == 1
    with pytest.raises(PassUnavailableError, match="not_yet_valid") as err:
        await manager.async_get_valid(guest_pass["pass_id"], secret)
    assert err.value.valid_from == valid_from.isoformat()
    assert err.value.label == "Morgen"

    current[0] = valid_from
    assert (await manager.async_get_valid(guest_pass["pass_id"], secret))["active"]

    current[0] += timedelta(hours=2)
    with pytest.raises(PassUnavailableError, match="expired"):
        await manager.async_get_valid(guest_pass["pass_id"], secret)


@pytest.mark.asyncio
async def test_wrong_secret_is_rejected() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()
    guest_pass, _secret = await manager.async_create(
        label="Gast", duration_hours=1, max_uses=1
    )

    with pytest.raises(PassUnavailableError, match="invalid"):
        await manager.async_get_valid(guest_pass["pass_id"], "wrong-secret")


@pytest.mark.asyncio
async def test_revoke_during_reserved_action_still_allows_commit() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()
    guest_pass, secret = await manager.async_create(
        label="Gast", duration_hours=1, max_uses=1
    )

    await manager.async_reserve_use(guest_pass["pass_id"], secret)
    assert await manager.async_revoke(guest_pass["pass_id"]) is True
    committed = await manager.async_commit_use(guest_pass["pass_id"])

    assert committed["use_count"] == 1
    assert committed["active"] is False


@pytest.mark.asyncio
async def test_activity_is_persistent_newest_first_and_contains_no_secret() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()
    guest_pass, secret = await manager.async_create(
        label="Paketdienst", duration_hours=1, max_uses=2
    )

    await manager.async_reserve_use(guest_pass["pass_id"], secret)
    await manager.async_commit_use(guest_pass["pass_id"])

    reloaded = PassManager(storage)
    await reloaded.async_load()
    activity = await reloaded.async_list_activity()

    assert [item["event_type"] for item in activity] == ["used", "created"]
    assert activity[0]["label"] == "Paketdienst"
    assert activity[0]["use_count"] == 1
    assert secret not in str(storage.data)
    assert all("secret" not in item for item in activity)


@pytest.mark.asyncio
async def test_revoke_is_recorded_and_activity_can_be_cleared() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()
    guest_pass, _secret = await manager.async_create(
        label="Gast", duration_hours=1, max_uses=1
    )

    assert await manager.async_revoke(guest_pass["pass_id"])
    assert [item["event_type"] for item in await manager.async_list_activity()] == [
        "revoked",
        "created",
    ]
    assert await manager.async_clear_activity() == 2
    assert await manager.async_list_activity() == []
    assert storage.data is not None
    assert storage.data["activity"] == []


@pytest.mark.asyncio
async def test_activity_retains_only_the_latest_200_records() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()

    for index in range(205):
        await manager.async_create(label=f"Gast {index}", duration_hours=1, max_uses=1)

    activity = await manager.async_list_activity()
    assert len(activity) == 200
    assert activity[0]["label"] == "Gast 204"
    assert activity[-1]["label"] == "Gast 5"


@pytest.mark.asyncio
async def test_creator_only_sees_and_revokes_owned_passes() -> None:
    storage = MemoryStorage()
    manager = PassManager(storage)
    await manager.async_load()
    alice_pass, _secret = await manager.async_create(
        label="Alice", duration_hours=1, max_uses=1, created_by_user_id="alice"
    )
    bob_pass, _secret = await manager.async_create(
        label="Bob", duration_hours=1, max_uses=1, created_by_user_id="bob"
    )
    await manager.async_create(label="Legacy", duration_hours=1, max_uses=1)

    alice_passes = await manager.async_list_active(owner_user_id="alice")
    alice_activity = await manager.async_list_activity(owner_user_id="alice")

    assert [item["pass_id"] for item in alice_passes] == [alice_pass["pass_id"]]
    assert [item["label"] for item in alice_activity] == ["Alice"]
    assert "created_by_user_id" not in alice_passes[0]
    assert "created_by_user_id" not in alice_activity[0]
    assert not await manager.async_revoke(bob_pass["pass_id"], owner_user_id="alice")
    assert await manager.async_revoke(alice_pass["pass_id"], owner_user_id="alice")
    assert [item["label"] for item in await manager.async_list_active()] == [
        "Bob",
        "Legacy",
    ]


async def test_terminal_records_are_bounded_without_removing_active_passes():
    from custom_components.gate_pass.const import TERMINAL_PASS_LIMIT

    from .test_server_http import SnapshotStorage

    storage = SnapshotStorage()
    manager = PassManager(storage)
    active, secret = await manager.async_create(
        label="active", duration_hours=1, max_uses=1
    )
    for _ in range(TERMINAL_PASS_LIMIT + 10):
        record, _ = await manager.async_create(
            label="old", duration_hours=1, max_uses=1
        )
        await manager.async_revoke(record["pass_id"])
    assert len(storage.data["passes"]) == TERMINAL_PASS_LIMIT + 1
    assert (await manager.async_get_valid(active["pass_id"], secret))["active"]
    assert len(await manager.async_list_activity()) <= 200


async def test_load_purges_existing_terminal_records():
    from custom_components.gate_pass.const import TERMINAL_PASS_LIMIT

    from .test_server_http import SnapshotStorage

    storage = SnapshotStorage()
    storage.data = {
        "passes": [
            {"pass_id": str(index), "active": False}
            for index in range(TERMINAL_PASS_LIMIT + 100)
        ]
    }
    manager = PassManager(storage)
    await manager.async_load()
    assert len(storage.data["passes"]) == TERMINAL_PASS_LIMIT


async def test_legacy_store_adopts_action_once_and_normal_reload_preserves_links():
    from .test_server_http import SnapshotStorage

    storage = SnapshotStorage()
    legacy = PassManager(storage)
    record, secret = await legacy.async_create(
        label="old", duration_hours=1, max_uses=1
    )
    action = ("button.garage", "button.press")
    upgraded = PassManager(storage, action=action)
    await upgraded.async_load()
    assert storage.data["action"] == list(action)
    reloaded = PassManager(storage, action=action)
    await reloaded.async_load()
    assert (await reloaded.async_get_valid(record["pass_id"], secret))["active"]


async def test_shutdown_waits_for_persistence_not_just_action():
    import asyncio

    from .test_server_http import SnapshotStorage

    storage = SnapshotStorage()
    manager = PassManager(storage)
    record, secret = await manager.async_create(
        label="test", duration_hours=1, max_uses=1
    )
    await manager.async_reserve_use(record["pass_id"], secret)
    saving, finish = asyncio.Event(), asyncio.Event()
    original_save = storage.async_save

    async def slow_save(data):
        saving.set()
        await finish.wait()
        await original_save(data)

    storage.async_save = slow_save
    commit = asyncio.create_task(manager.async_commit_use(record["pass_id"]))
    await saving.wait()
    shutdown = asyncio.create_task(manager.async_shutdown())
    await asyncio.sleep(0)
    assert not shutdown.done()
    finish.set()
    await commit
    await asyncio.wait_for(shutdown, 2)
    assert storage.data["passes"][0]["use_count"] == 1
    with pytest.raises(PassUnavailableError):
        await manager.async_create(label="late", duration_hours=1, max_uses=1)


async def test_cancelled_commit_finishes_persistence_before_shutdown():
    import asyncio

    from .test_server_http import SnapshotStorage

    storage = SnapshotStorage()
    manager = PassManager(storage)
    record, secret = await manager.async_create(
        label="once", duration_hours=1, max_uses=1
    )
    await manager.async_reserve_use(record["pass_id"], secret)
    saving, finish = asyncio.Event(), asyncio.Event()
    original_save = storage.async_save

    async def slow_save(data):
        saving.set()
        await finish.wait()
        await original_save(data)

    storage.async_save = slow_save
    commit = asyncio.create_task(manager.async_commit_use(record["pass_id"]))
    await asyncio.wait_for(saving.wait(), 2)
    commit.cancel()
    shutdown = asyncio.create_task(manager.async_shutdown())
    await asyncio.sleep(0)
    assert not shutdown.done()
    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await commit
    await asyncio.wait_for(shutdown, 2)
    assert storage.data["passes"][0]["use_count"] == 1
