"""Home Assistant status sensors for Gate Pass access points."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GatePassRuntime, get_runtime
from .const import (
    CONF_ACCESS_NAME,
    CONF_EXPOSE_LAST_USED_LABEL,
    DEFAULT_EXPOSE_LAST_USED_LABEL,
    DOMAIN,
    EVENT_ACTIVITY_CLEARED,
    EVENT_PASS_CREATED,
    EVENT_PASS_REVOKED,
    EVENT_PASS_USED,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up status sensors for one access point."""
    runtime = get_runtime(hass, entry.entry_id)
    active = await runtime.manager.async_list_active()
    activity = await runtime.manager.async_list_activity()
    last_used = next(
        (item for item in activity if item.get("event_type") == "used"), None
    )
    async_add_entities(
        [
            GatePassActivePassesSensor(runtime, len(active)),
            GatePassLastUsedSensor(runtime, last_used),
        ]
    )


class GatePassSensor(SensorEntity):
    """Base class for access-point scoped sensors."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, runtime: GatePassRuntime, key: str, name: str) -> None:
        self.runtime = runtime
        self._attr_unique_id = f"{runtime.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, runtime.entry_id)},
            name=str(runtime.config[CONF_ACCESS_NAME]),
            manufacturer="Gate Pass HA",
            model="Access point",
        )

    def _matches(self, event: Event) -> bool:
        return event.data.get("config_entry_id") == self.runtime.entry_id


class GatePassActivePassesSensor(GatePassSensor):
    """Count active or scheduled passes."""

    _attr_icon = "mdi:ticket-confirmation-outline"
    _attr_should_poll = True

    def __init__(self, runtime: GatePassRuntime, count: int) -> None:
        super().__init__(runtime, "active_passes", "Active passes")
        self._attr_native_value = count

    async def async_added_to_hass(self) -> None:
        """Listen for pass lifecycle changes."""
        await super().async_added_to_hass()
        for event_type in (EVENT_PASS_CREATED, EVENT_PASS_REVOKED, EVENT_PASS_USED):
            self.async_on_remove(
                self.hass.bus.async_listen(event_type, self._handle_event)
            )

    @callback
    def _handle_event(self, event: Event) -> None:
        if self._matches(event):
            self.hass.async_create_task(self._async_refresh())

    async def async_update(self) -> None:
        """Refresh expiry state during Home Assistant's normal local polling."""
        self._attr_native_value = len(await self.runtime.manager.async_list_active())

    async def _async_refresh(self) -> None:
        await self.async_update()
        self.async_write_ha_state()


class GatePassLastUsedSensor(GatePassSensor):
    """Timestamp and summary of the last successful use."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:door-open"

    def __init__(
        self, runtime: GatePassRuntime, activity: dict[str, Any] | None
    ) -> None:
        super().__init__(runtime, "last_used", "Last used")
        self._label: str | None = None
        self._use_count: int | None = None
        self._set_activity(activity)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose a privacy-conscious use summary."""
        attributes: dict[str, Any] = {"use_count": self._use_count}
        if bool(
            self.runtime.config.get(
                CONF_EXPOSE_LAST_USED_LABEL, DEFAULT_EXPOSE_LAST_USED_LABEL
            )
        ):
            attributes["label"] = self._label
        return attributes

    async def async_added_to_hass(self) -> None:
        """Listen for successful use and history clearing."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_PASS_USED, self._handle_used)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(
                EVENT_ACTIVITY_CLEARED, self._handle_activity_cleared
            )
        )

    @callback
    def _handle_used(self, event: Event) -> None:
        if not self._matches(event):
            return
        self._attr_native_value = datetime.fromisoformat(event.time_fired.isoformat())
        self._label = str(event.data.get("label", "")) or None
        self._use_count = int(event.data.get("use_count", 0))
        self.async_write_ha_state()

    @callback
    def _handle_activity_cleared(self, event: Event) -> None:
        if self._matches(event):
            self._set_activity(None)
            self.async_write_ha_state()

    def _set_activity(self, activity: dict[str, Any] | None) -> None:
        if not activity:
            self._attr_native_value = None
            self._label = None
            self._use_count = None
            return
        try:
            self._attr_native_value = datetime.fromisoformat(
                str(activity["occurred_at"])
            )
        except (KeyError, TypeError, ValueError):
            self._attr_native_value = None
        self._label = str(activity.get("label", "")) or None
        self._use_count = int(activity.get("use_count", 0))
