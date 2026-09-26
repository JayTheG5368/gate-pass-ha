"""Test the real HA setup/unload functions with narrow HA API doubles."""

import asyncio
import importlib.util
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.gate_pass.const import (
    CONF_ACCESS_NAME,
    CONF_ENTITY_ID,
    CONF_GUEST_PORT,
    CONF_SERVICE,
    DATA_RUNTIMES,
    DATA_SERVER_LOCKS,
    DATA_SERVERS,
    DOMAIN,
)
from custom_components.gate_pass.pass_manager import PassUnavailableError
from custom_components.gate_pass.server import GuestServer

from .test_server_http import SnapshotStorage


@pytest.fixture
def integration(monkeypatch):
    def module(name, **attributes):
        value = ModuleType(name)
        value.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, value)
        return value

    module("homeassistant.components")
    module("homeassistant.components.http", StaticPathConfig=object)
    module("homeassistant.config_entries", ConfigEntry=object)
    module("homeassistant.const", EVENT_HOMEASSISTANT_STOP="stop")
    module(
        "homeassistant.core",
        HomeAssistant=object,
        ServiceCall=object,
        ServiceResponse=dict,
        SupportsResponse=object,
    )
    module(
        "homeassistant.exceptions",
        ConfigEntryNotReady=RuntimeError,
        ServiceValidationError=ValueError,
        Unauthorized=PermissionError,
        UnknownUser=PermissionError,
    )
    cv = module(
        "homeassistant.helpers.config_validation",
        config_entry_only_config_schema=lambda domain: {},
    )
    monkeypatch.setattr(
        sys.modules["homeassistant.helpers"], "config_validation", cv, raising=False
    )
    module("homeassistant.helpers.typing", ConfigType=dict)
    name = "custom_components.gate_pass._integration_test"
    path = Path(__file__).parents[1] / "custom_components/gate_pass/__init__.py"
    spec = importlib.util.spec_from_loader(
        name, SourceFileLoader(name, str(path)), is_package=False
    )
    loaded = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, loaded)
    spec.loader.exec_module(loaded)
    return loaded


async def test_actual_unload_drains_shared_server_before_new_manager_loads(
    integration, monkeypatch
):
    storage = SnapshotStorage()
    monkeypatch.setattr(
        integration, "HomeAssistantPassStorage", lambda *a, **kw: storage
    )
    entry = SimpleNamespace(
        entry_id="one",
        title="Garage",
        options={},
        data={
            CONF_ACCESS_NAME: "Garage",
            CONF_ENTITY_ID: "button.garage",
            CONF_SERVICE: "button.press",
            CONF_GUEST_PORT: 8922,
        },
        async_on_unload=Mock(),
        add_update_listener=Mock(),
    )
    hass = SimpleNamespace(
        data={DOMAIN: {DATA_RUNTIMES: {}, DATA_SERVERS: {}, DATA_SERVER_LOCKS: {}}},
        config_entries=SimpleNamespace(
            async_entries=lambda domain: [entry],
            async_forward_entry_setups=AsyncMock(),
            async_unload_platforms=AsyncMock(return_value=True),
        ),
        bus=SimpleNamespace(async_listen_once=Mock()),
    )
    server = GuestServer(hass, 8922)
    server.register("other", object(), {})
    hass.data[DOMAIN][DATA_SERVERS][8922] = server
    assert await integration.async_setup_entry(hass, entry)
    old = hass.data[DOMAIN][DATA_RUNTIMES]["one"].manager
    record, secret = await old.async_create(label="once", duration_hours=1, max_uses=1)
    await old.async_reserve_use(record["pass_id"], secret)
    unload = asyncio.create_task(integration.async_unload_entry(hass, entry))
    await asyncio.sleep(0)
    assert not unload.done()
    await old.async_commit_use(record["pass_id"])
    assert await asyncio.wait_for(unload, 2)
    assert await integration.async_setup_entry(hass, entry)
    new = hass.data[DOMAIN][DATA_RUNTIMES]["one"].manager
    with pytest.raises(PassUnavailableError):
        await new.async_reserve_use(record["pass_id"], secret)

    active, secret = await new.async_create(
        label="garage only", duration_hours=1, max_uses=1
    )
    assert await integration.async_unload_entry(hass, entry)
    entry.options = {CONF_ENTITY_ID: "button.front_door"}
    assert await integration.async_setup_entry(hass, entry)
    changed = hass.data[DOMAIN][DATA_RUNTIMES]["one"].manager
    with pytest.raises(PassUnavailableError):
        await changed.async_get_valid(active["pass_id"], secret)
