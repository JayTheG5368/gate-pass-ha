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
