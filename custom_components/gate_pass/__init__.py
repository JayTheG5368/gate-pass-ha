"""Gate Pass HA integration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DURATION_HOURS,
    ATTR_LABEL,
    ATTR_MAX_USES,
    ATTR_PASS_ID,
    ATTR_VALID_FROM,
    CARD_URL,
    CONF_ACCESS_NAME,
    CONF_DEFAULT_DURATION_HOURS,
    CONF_DEFAULT_MAX_USES,
    DEFAULT_DURATION_HOURS,
    DEFAULT_MAX_USES,
    DOMAIN,
    EVENT_PASS_CREATED,
    EVENT_PASS_REVOKED,
    SERVICE_CREATE_PASS,
    SERVICE_LIST_PASSES,
    SERVICE_REVOKE_ALL,
    SERVICE_REVOKE_PASS,
)
from .pass_manager import PassManager
from .server import GuestServer
from .storage import HomeAssistantPassStorage

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class GatePassRuntime:
    """Runtime data for the single Gate Pass config entry."""

    config: dict[str, Any]
    manager: PassManager
    server: GuestServer


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the card resource and integration services."""
    hass.data.setdefault(DOMAIN, {})
    frontend_path = Path(__file__).parent / "frontend" / "gate-pass-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(frontend_path), False)]
    )

    if hass.services.has_service(DOMAIN, SERVICE_CREATE_PASS):
        return True

    async def async_create_pass(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass)
        duration = float(
            call.data.get(
                ATTR_DURATION_HOURS,
                runtime.config.get(CONF_DEFAULT_DURATION_HOURS, DEFAULT_DURATION_HOURS),
            )
        )
        max_uses = int(
            call.data.get(
                ATTR_MAX_USES,
                runtime.config.get(CONF_DEFAULT_MAX_USES, DEFAULT_MAX_USES),
            )
        )
        guest_pass, secret = await runtime.manager.async_create(
            label=str(call.data.get(ATTR_LABEL, "Gast")),
            duration_hours=duration,
            max_uses=max_uses,
            valid_from=call.data.get(ATTR_VALID_FROM),
        )
        guest_url = runtime.server.build_guest_url(guest_pass["pass_id"], secret)
        hass.bus.async_fire(
            EVENT_PASS_CREATED,
            {"pass_id": guest_pass["pass_id"], "label": guest_pass["label"]},
        )
        response = {
            "pass_id": guest_pass["pass_id"],
            "label": guest_pass["label"],
            "guest_url": guest_url,
            "expires_at": guest_pass["expires_at"],
            "valid_from": guest_pass["valid_from"],
            "max_uses": guest_pass["max_uses"],
        }
        return response if call.return_response else None

    async def async_list_passes(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass)
        return {
            "access_name": runtime.config[CONF_ACCESS_NAME],
            "passes": await runtime.manager.async_list_active(),
        }

    async def async_revoke_pass(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass)
        pass_id = str(call.data[ATTR_PASS_ID])
        revoked = await runtime.manager.async_revoke(pass_id)
        if not revoked:
            raise ServiceValidationError("Pass not found")
        hass.bus.async_fire(EVENT_PASS_REVOKED, {"pass_id": pass_id})
        response = {"success": True}
        return response if call.return_response else None

    async def async_revoke_all(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass)
        count = await runtime.manager.async_revoke_all()
        hass.bus.async_fire(EVENT_PASS_REVOKED, {"all": True, "count": count})
        response = {"success": True, "count": count}
        return response if call.return_response else None

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_CREATE_PASS,
        async_create_pass,
        schema=vol.Schema(
            {
                vol.Optional(ATTR_LABEL): vol.All(cv.string, vol.Length(max=80)),
                vol.Optional(ATTR_DURATION_HOURS): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=720)
                ),
                vol.Optional(ATTR_MAX_USES): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=1000)
                ),
                vol.Optional(ATTR_VALID_FROM): cv.datetime,
            }
        ),
        supports_response=SupportsResponse.OPTIONAL,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_LIST_PASSES,
        async_list_passes,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REVOKE_PASS,
        async_revoke_pass,
        schema=vol.Schema({vol.Required(ATTR_PASS_ID): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_REVOKE_ALL,
        async_revoke_all,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gate Pass from a config entry."""
    merged_config = {**entry.data, **entry.options}
    manager = PassManager(HomeAssistantPassStorage(hass))
    await manager.async_load()
    server = GuestServer(hass, manager, merged_config)
    try:
        await server.async_start()
    except OSError as err:
        await server.async_stop()
        raise ConfigEntryNotReady(
            f"Could not bind Gate Pass guest port: {err}"
        ) from err

    runtime = GatePassRuntime(merged_config, manager, server)
    hass.data[DOMAIN][entry.entry_id] = runtime
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _on_stop(_event: Any) -> None:
        await server.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Gate Pass and release the guest port."""
    runtime: GatePassRuntime | None = hass.data.get(DOMAIN, {}).pop(
        entry.entry_id, None
    )
    if runtime is not None:
        await runtime.server.async_stop()
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload Gate Pass when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_runtime(hass: HomeAssistant) -> GatePassRuntime:
    runtimes = list(hass.data.get(DOMAIN, {}).values())
    if len(runtimes) != 1 or not isinstance(runtimes[0], GatePassRuntime):
        raise ServiceValidationError("Gate Pass is not configured or loaded")
    return runtimes[0]
