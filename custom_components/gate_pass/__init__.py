"""Gate Pass HA integration."""

from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass
from io import StringIO
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
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    ServiceValidationError,
    Unauthorized,
    UnknownUser,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_DURATION_HOURS,
    ATTR_LABEL,
    ATTR_MAX_USES,
    ATTR_PASS_ID,
    ATTR_VALID_FROM,
    CARD_URL,
    CONF_ACCESS_NAME,
    CONF_ACTION_LABEL,
    CONF_DEFAULT_DURATION_HOURS,
    CONF_DEFAULT_MAX_USES,
    CONF_ENTITY_ID,
    CONF_GUEST_PORT,
    CONF_PUBLIC_BASE_URL,
    CONF_SERVICE,
    DATA_RUNTIMES,
    DATA_SERVER_LOCKS,
    DATA_SERVERS,
    DEFAULT_DURATION_HOURS,
    DEFAULT_MAX_USES,
    DOMAIN,
    EVENT_ACTIVITY_CLEARED,
    EVENT_PASS_CREATED,
    EVENT_PASS_REVOKED,
    PLATFORMS,
    SERVICE_CLEAR_ACTIVITY,
    SERVICE_CREATE_PASS,
    SERVICE_EXPORT_ACTIVITY,
    SERVICE_LIST_ACCESS_POINTS,
    SERVICE_LIST_ACTIVITY,
    SERVICE_LIST_PASSES,
    SERVICE_REVOKE_ALL,
    SERVICE_REVOKE_PASS,
)
from .csv_export import csv_safe_activity
from .notifications import async_send_notification
from .pass_manager import PassManager
from .permissions import (
    AccessRights,
    access_rights,
    creation_limits,
    validate_creation_request,
)
from .server import GuestServer
from .storage import HomeAssistantPassStorage

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class GatePassRuntime:
    """Runtime data for one configured access point."""

    entry_id: str
    config: dict[str, Any]
    manager: PassManager
    server: GuestServer


@dataclass(frozen=True)
class RequestIdentity:
    """Authenticated Home Assistant service caller."""

    user_id: str | None
    is_admin: bool


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the card resource and permission-checked services."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data.setdefault(DATA_RUNTIMES, {})
    domain_data.setdefault(DATA_SERVERS, {})
    domain_data.setdefault(DATA_SERVER_LOCKS, {})

    frontend_path = Path(__file__).parent / "frontend" / "gate-pass-card.js"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(frontend_path), False)]
    )

    if hass.services.has_service(DOMAIN, SERVICE_CREATE_PASS):
        return True

    async def async_list_access_points(call: ServiceCall) -> ServiceResponse:
        identity = await _async_request_identity(hass, call)
        runtimes = _runtimes(hass)
        access_points = []
        for runtime in sorted(
            runtimes.values(),
            key=lambda item: str(item.config[CONF_ACCESS_NAME]).casefold(),
        ):
            rights = access_rights(
                runtime.config, identity.user_id, is_admin=identity.is_admin
            )
            if not rights.can_create and not rights.can_manage:
                continue
            access_points.append(
                {
                    "config_entry_id": runtime.entry_id,
                    "access_name": runtime.config[CONF_ACCESS_NAME],
                    "action_label": runtime.config[CONF_ACTION_LABEL],
                    "guest_port": runtime.config[CONF_GUEST_PORT],
                    "public_base_url": runtime.config.get(CONF_PUBLIC_BASE_URL, ""),
                    "permissions": rights.as_dict(),
                    "creation_limits": creation_limits(
                        runtime.config, is_admin=identity.is_admin
                    ).as_dict(),
                }
            )
        return {"access_points": access_points}

    async def async_create_pass(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass, call)
        identity, _rights = await _async_require_access(hass, call, runtime)
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
        limits = creation_limits(runtime.config, is_admin=identity.is_admin)
        try:
            validate_creation_request(
                limits, duration_hours=duration, max_uses=max_uses
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        guest_pass, secret = await runtime.manager.async_create(
            label=str(call.data.get(ATTR_LABEL, "Gast")),
            duration_hours=duration,
            max_uses=max_uses,
            valid_from=call.data.get(ATTR_VALID_FROM),
            created_by_user_id=identity.user_id,
        )
        guest_url = runtime.server.build_guest_url(
            runtime.entry_id, guest_pass["pass_id"], secret
        )
        event_data = _event_data(runtime, pass_id=guest_pass["pass_id"])
        event_data["label"] = guest_pass["label"]
        hass.bus.async_fire(EVENT_PASS_CREATED, event_data)
        await async_send_notification(
            hass, runtime.config, "created", label=guest_pass["label"]
        )
        response = {
            "config_entry_id": runtime.entry_id,
            "access_name": runtime.config[CONF_ACCESS_NAME],
            "pass_id": guest_pass["pass_id"],
            "label": guest_pass["label"],
            "guest_url": guest_url,
            "expires_at": guest_pass["expires_at"],
            "valid_from": guest_pass["valid_from"],
            "max_uses": guest_pass["max_uses"],
        }
        return response if call.return_response else None

    async def async_list_passes(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass, call)
        _identity, rights = await _async_require_access(hass, call, runtime)
        return {
            "config_entry_id": runtime.entry_id,
            "access_name": runtime.config[CONF_ACCESS_NAME],
            "passes": await runtime.manager.async_list_active(
                owner_user_id=rights.owner_user_id
            ),
            "permissions": rights.as_dict(),
        }

    async def async_list_activity(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass, call)
        _identity, rights = await _async_require_access(hass, call, runtime)
        return {
            "config_entry_id": runtime.entry_id,
            "access_name": runtime.config[CONF_ACCESS_NAME],
            "activity": await runtime.manager.async_list_activity(
                owner_user_id=rights.owner_user_id
            ),
            "permissions": rights.as_dict(),
        }

    async def async_export_activity(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass, call)
        await _async_require_access(hass, call, runtime, require_manage=True)
        output = StringIO(newline="")
        fieldnames = (
            "event_type",
            "occurred_at",
            "label",
            "pass_id",
            "use_count",
            "max_uses",
        )
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(
            csv_safe_activity(item)
            for item in await runtime.manager.async_list_activity()
        )
        return {
            "filename": f"gate-pass-activity-{runtime.entry_id[:8]}.csv",
            "content_type": "text/csv;charset=utf-8",
            "csv": output.getvalue(),
        }

    async def async_clear_activity(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass, call)
        await _async_require_access(hass, call, runtime, require_manage=True)
        count = await runtime.manager.async_clear_activity()
        event_data = _event_data(runtime, count=count)
        hass.bus.async_fire(EVENT_ACTIVITY_CLEARED, event_data)
        response = {"success": True, "count": count}
        return response if call.return_response else None

    async def async_revoke_pass(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass, call)
        _identity, rights = await _async_require_access(hass, call, runtime)
        pass_id = str(call.data[ATTR_PASS_ID])
        active_passes = await runtime.manager.async_list_active(
            owner_user_id=rights.owner_user_id
        )
        label = next(
            (item["label"] for item in active_passes if item["pass_id"] == pass_id),
            pass_id,
        )
        revoked = await runtime.manager.async_revoke(
            pass_id, owner_user_id=rights.owner_user_id
        )
        if not revoked:
            raise ServiceValidationError("Pass not found")
        event_data = _event_data(runtime, pass_id=pass_id)
        event_data["label"] = label
        hass.bus.async_fire(EVENT_PASS_REVOKED, event_data)
        await async_send_notification(hass, runtime.config, "revoked", label=str(label))
        response = {"success": True}
        return response if call.return_response else None

    async def async_revoke_all(call: ServiceCall) -> ServiceResponse:
        runtime = _get_runtime(hass, call)
        await _async_require_access(hass, call, runtime, require_manage=True)
        count = await runtime.manager.async_revoke_all()
        event_data = _event_data(runtime, all=True, count=count)
        hass.bus.async_fire(EVENT_PASS_REVOKED, event_data)
        if count:
            await async_send_notification(hass, runtime.config, "revoked", count=count)
        response = {"success": True, "count": count}
        return response if call.return_response else None

    runtime_field = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
    hass.services.async_register(
        DOMAIN,
        SERVICE_LIST_ACCESS_POINTS,
        async_list_access_points,
        schema=vol.Schema({}),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_PASS,
        async_create_pass,
        schema=vol.Schema(
            {
                **runtime_field,
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
    for service, handler in (
        (SERVICE_LIST_PASSES, async_list_passes),
        (SERVICE_LIST_ACTIVITY, async_list_activity),
        (SERVICE_EXPORT_ACTIVITY, async_export_activity),
    ):
        hass.services.async_register(
            DOMAIN,
            service,
            handler,
            schema=vol.Schema(runtime_field),
            supports_response=SupportsResponse.ONLY,
        )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_ACTIVITY,
        async_clear_activity,
        schema=vol.Schema(runtime_field),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REVOKE_PASS,
        async_revoke_pass,
        schema=vol.Schema({**runtime_field, vol.Required(ATTR_PASS_ID): cv.string}),
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REVOKE_ALL,
        async_revoke_all,
        schema=vol.Schema(runtime_field),
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one Gate Pass access point."""
    domain_data = hass.data[DOMAIN]
    runtimes: dict[str, GatePassRuntime] = domain_data[DATA_RUNTIMES]
    servers: dict[int, GuestServer] = domain_data[DATA_SERVERS]
    server_locks: dict[int, asyncio.Lock] = domain_data[DATA_SERVER_LOCKS]
    merged_config = {**entry.data, **entry.options}

    entries = hass.config_entries.async_entries(DOMAIN)
    legacy_owner = bool(entries and entries[0].entry_id == entry.entry_id)
    manager = PassManager(
        HomeAssistantPassStorage(hass, entry.entry_id, migrate_legacy=legacy_owner),
        action=(merged_config[CONF_ENTITY_ID], merged_config[CONF_SERVICE]),
    )
    await manager.async_load()

    port = int(merged_config[CONF_GUEST_PORT])
    server_lock = server_locks.setdefault(port, asyncio.Lock())
    async with server_lock:
        server = servers.get(port)
        if server is None:
            server = GuestServer(hass, port)
            server.register(entry.entry_id, manager, merged_config, legacy=legacy_owner)
            try:
                await server.async_start()
            except OSError as err:
                server.unregister(entry.entry_id)
                await server.async_stop()
                raise ConfigEntryNotReady(
                    f"Could not bind Gate Pass guest port: {err}"
                ) from err
            servers[port] = server
        else:
            server.register(entry.entry_id, manager, merged_config, legacy=legacy_owner)

    runtime = GatePassRuntime(entry.entry_id, merged_config, manager, server)
    runtimes[entry.entry_id] = runtime
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        runtimes.pop(entry.entry_id, None)
        async with server_lock:
            await manager.async_shutdown()
            server.unregister(entry.entry_id)
            if server.empty:
                servers.pop(port, None)
                await server.async_stop()
        raise

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    async def _on_stop(_event: Any) -> None:
        async with server_lock:
            await server.async_stop()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_stop)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one access point and release an unused guest port."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    domain_data = hass.data.get(DOMAIN, {})
    runtime = domain_data.get(DATA_RUNTIMES, {}).pop(entry.entry_id, None)
    if not isinstance(runtime, GatePassRuntime):
        return True

    port = int(runtime.config[CONF_GUEST_PORT])
    server_locks: dict[int, asyncio.Lock] = domain_data.get(DATA_SERVER_LOCKS, {})
    server_lock = server_locks.setdefault(port, asyncio.Lock())
    async with server_lock:
        await runtime.manager.async_shutdown()
        runtime.server.unregister(entry.entry_id)
        if runtime.server.empty:
            domain_data.get(DATA_SERVERS, {}).pop(port, None)
            await runtime.server.async_stop()
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload one access point when its options change."""
    access_name = str(entry.options.get(CONF_ACCESS_NAME, entry.data[CONF_ACCESS_NAME]))
    if entry.title != access_name:
        hass.config_entries.async_update_entry(entry, title=access_name)
    await hass.config_entries.async_reload(entry.entry_id)


def get_runtime(hass: HomeAssistant, entry_id: str) -> GatePassRuntime:
    """Return one loaded runtime for platform setup."""
    runtime = _runtimes(hass).get(entry_id)
    if not isinstance(runtime, GatePassRuntime):
        raise ConfigEntryNotReady("Gate Pass access point is not loaded")
    return runtime


def _runtimes(hass: HomeAssistant) -> dict[str, GatePassRuntime]:
    return hass.data.get(DOMAIN, {}).get(DATA_RUNTIMES, {})


async def _async_request_identity(
    hass: HomeAssistant, call: ServiceCall
) -> RequestIdentity:
    """Resolve a service caller, preserving trusted internal HA calls."""
    user_id = call.context.user_id
    if not user_id:
        return RequestIdentity(None, True)
    user = await hass.auth.async_get_user(user_id)
    if user is None:
        raise UnknownUser(context=call.context)
    return RequestIdentity(user_id, bool(user.is_admin))


async def _async_require_access(
    hass: HomeAssistant,
    call: ServiceCall,
    runtime: GatePassRuntime,
    *,
    require_manage: bool = False,
) -> tuple[RequestIdentity, AccessRights]:
    """Authorize one service call for the selected access point."""
    identity = await _async_request_identity(hass, call)
    rights = access_rights(runtime.config, identity.user_id, is_admin=identity.is_admin)
    allowed = rights.can_manage if require_manage else rights.can_create
    if not allowed:
        raise Unauthorized(context=call.context)
    return identity, rights


def _get_runtime(hass: HomeAssistant, call: ServiceCall) -> GatePassRuntime:
    runtimes = _runtimes(hass)
    entry_id = str(call.data.get(ATTR_CONFIG_ENTRY_ID, "")).strip()
    if entry_id:
        runtime = runtimes.get(entry_id)
        if isinstance(runtime, GatePassRuntime):
            return runtime
        raise ServiceValidationError("Selected Gate Pass access point is not loaded")
    if len(runtimes) == 1:
        return next(iter(runtimes.values()))
    if not runtimes:
        raise ServiceValidationError("Gate Pass is not configured or loaded")
    raise ServiceValidationError(
        "Multiple Gate Pass access points are loaded; select config_entry_id"
    )


def _event_data(runtime: GatePassRuntime, **data: Any) -> dict[str, Any]:
    return {
        "config_entry_id": runtime.entry_id,
        "access_name": runtime.config[CONF_ACCESS_NAME],
        **data,
    }
