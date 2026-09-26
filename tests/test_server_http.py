"""Exercise public routes through a real aiohttp server and client."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from custom_components.gate_pass.const import (
    CONF_ACCESS_NAME,
    CONF_ACTION_LABEL,
    CONF_ENTITY_ID,
    CONF_PUBLIC_BASE_URL,
    CONF_SERVICE,
)
from custom_components.gate_pass.pass_manager import PassManager, PassUnavailableError
from custom_components.gate_pass.server import GuestServer


class SnapshotStorage:
    """Serialize copies so a fresh manager cannot see unsaved mutations."""

    def __init__(self):
        self.data = None

    async def async_load(self):
        return deepcopy(self.data)

    async def async_save(self, data):
        self.data = deepcopy(data)


@pytest.fixture
async def guest():
    storage = SnapshotStorage()
    config = {
        CONF_ACCESS_NAME: "Garage",
        CONF_ACTION_LABEL: "Open",
        CONF_ENTITY_ID: "button.garage",
        CONF_SERVICE: "button.press",
        CONF_PUBLIC_BASE_URL: "https://gate.test",
    }
    manager = PassManager(storage, action=("button.garage", "button.press"))
    await manager.async_load()
    hass = SimpleNamespace(
        services=SimpleNamespace(
            has_service=Mock(return_value=True), async_call=AsyncMock()
        ),
        bus=SimpleNamespace(async_fire=Mock()),
    )
    server = GuestServer(hass, 0)
    server.register("one", manager, config)
    async with TestClient(TestServer(server.create_app())) as client:
        yield SimpleNamespace(
            manager=manager,
            storage=storage,
            server=server,
            hass=hass,
            config=config,
            client=client,
        )


async def create(guest, max_uses=1, **kwargs):
    record, secret = await guest.manager.async_create(
        label="Guest", duration_hours=1, max_uses=max_uses, **kwargs
    )
    return record, f"/gate-pass/api/one/{record['pass_id']}/{secret}", secret


async def test_status_does_not_consume_and_success_is_persisted(guest):
    record, url, secret = await create(guest)
    response = await guest.client.get(url + "/status")
    assert response.status == 200
    assert (await response.json())["remaining_uses"] == 1
    assert response.headers["Cache-Control"] == "no-store"
    guest.hass.services.async_call.assert_not_called()
    response = await guest.client.post(url + "/open", json={})
    assert response.status == 200
    assert (await response.json())["remaining_uses"] == 0
    guest.hass.services.async_call.assert_awaited_once_with(
        "button", "press", {"entity_id": "button.garage"}, blocking=True
    )
    reloaded = PassManager(guest.storage, action=("button.garage", "button.press"))
    await reloaded.async_load()
    with pytest.raises(PassUnavailableError):
        await reloaded.async_get_valid(record["pass_id"], secret)
    assert (await guest.client.post(url + "/open", json={})).status == 401


@pytest.mark.parametrize("max_uses,remaining", [(2, 1), (0, None)])
async def test_success_reports_remaining_uses(guest, max_uses, remaining):
    _, url, _ = await create(guest, max_uses=max_uses)
    response = await guest.client.post(url + "/open", json={})
    assert (await response.json())["remaining_uses"] == remaining


@pytest.mark.parametrize(
    "body,content_type,status",
    [
        ("{}", "text/plain", 415),
        ("{", "application/json", 400),
        ("[]", "application/json", 400),
    ],
)
async def test_invalid_requests_never_act(guest, body, content_type, status):
    _, url, _ = await create(guest)
    response = await guest.client.post(
        url + "/open", data=body, headers={"Content-Type": content_type}
    )
    assert response.status == status
    guest.hass.services.async_call.assert_not_called()


async def test_origin_rejected_before_action(guest):
    _, url, _ = await create(guest)
    response = await guest.client.post(
        url + "/open", json={}, headers={"Origin": "https://evil.test"}
    )
    assert response.status == 403
    guest.hass.services.async_call.assert_not_called()


@pytest.mark.parametrize("unavailable", [True, False])
async def test_action_failure_does_not_consume_use(guest, unavailable):
    _, url, _ = await create(guest)
    if unavailable:
        guest.hass.services.has_service.return_value = False
    else:
        guest.hass.services.async_call.side_effect = RuntimeError("device offline")
    assert (await guest.client.post(url + "/open", json={})).status == 502
    assert (await (await guest.client.get(url + "/status")).json())[
        "remaining_uses"
    ] == 1
    guest.hass.services.has_service.return_value = True
    guest.hass.services.async_call.side_effect = None
    assert (await guest.client.post(url + "/open", json={})).status == 200


async def test_concurrent_request_and_reload_cannot_reuse_reservation(guest):
    _, url, _ = await create(guest)
    started, finish = asyncio.Event(), asyncio.Event()

    async def action(*args, **kwargs):
        started.set()
        await finish.wait()

    guest.hass.services.async_call.side_effect = action
    first = asyncio.create_task(guest.client.post(url + "/open", json={}))
    await asyncio.wait_for(started.wait(), 2)
    assert (await guest.client.post(url + "/open", json={})).status == 409
    shutdown = asyncio.create_task(guest.manager.async_shutdown())
    await asyncio.sleep(0)
    assert not shutdown.done()
    assert (await guest.client.post(url + "/open", json={})).status == 401
    finish.set()
    assert (await first).status == 200
    await asyncio.wait_for(shutdown, 2)
    guest.server.unregister("one")
    reloaded = PassManager(guest.storage, action=("button.garage", "button.press"))
    await reloaded.async_load()
    guest.server.register("one", reloaded, guest.config)
    assert (await guest.client.post(url + "/open", json={})).status == 401
    guest.hass.services.async_call.assert_awaited_once()


@pytest.mark.parametrize(
    "new_action",
    [
        ("button.front_door", "button.press"),
        ("button.garage", "button.other"),
    ],
)
async def test_target_change_revokes_old_link(guest, new_action):
    _, url, _ = await create(guest)
    await guest.manager.async_shutdown()
    reloaded = PassManager(guest.storage, action=new_action)
    await reloaded.async_load()
    guest.server.register(
        "one",
        reloaded,
        {
            **guest.config,
            CONF_ENTITY_ID: new_action[0],
            CONF_SERVICE: new_action[1],
        },
    )
    assert (await guest.client.post(url + "/open", json={})).status == 401
    guest.hass.services.async_call.assert_not_called()
    # Switching back must not revive the original credential.
    restored = PassManager(guest.storage, action=("button.garage", "button.press"))
    await restored.async_load()
    assert await restored.async_list_active() == []


async def test_scheduled_expired_and_wrong_credentials(guest):
    from datetime import datetime, timedelta, timezone

    _, url, _ = await create(
        guest, valid_from=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    assert (await guest.client.get(url + "/status")).status == 425
    assert (await guest.client.post(url + "/open", json={})).status == 425
    assert (await guest.client.get(url + "wrong/status")).status == 401
    guest.hass.services.async_call.assert_not_called()


async def test_cancelled_action_consumes_ambiguous_attempt_and_unblocks_shutdown(guest):
    record, _, secret = await create(guest)
    started = asyncio.Event()

    async def action(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    guest.hass.services.async_call.side_effect = action
    request = SimpleNamespace(
        match_info={"entry_id": "one", "pass_id": record["pass_id"], "secret": secret},
        headers={"Content-Type": "application/json"},
        json=AsyncMock(return_value={}),
    )
    task = asyncio.create_task(guest.server._handle_open(request))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(guest.manager.async_shutdown(), 2)
    assert guest.storage.data["passes"][0]["use_count"] == 1
