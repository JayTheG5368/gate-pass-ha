"""Home Assistant storage adapter for Gate Pass HA."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


class HomeAssistantPassStorage:
    """Persist passes in Home Assistant's protected storage directory."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> dict[str, Any] | None:
        """Load pass data."""
        return await self._store.async_load()

    async def async_save(self, data: dict[str, Any]) -> None:
        """Persist pass data."""
        await self._store.async_save(data)
