"""Home Assistant storage adapter for Gate Pass HA."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_MIGRATION_KEY, STORAGE_VERSION


class HomeAssistantPassStorage:
    """Persist one access point in Home Assistant's protected storage directory."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry_id: str,
        *,
        migrate_legacy: bool = False,
    ) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}.{config_entry_id}"
        )
        self._legacy_store: Store[dict[str, Any]] | None = (
            Store(hass, STORAGE_VERSION, STORAGE_KEY) if migrate_legacy else None
        )
        self._migration_store: Store[dict[str, Any]] | None = (
            Store(hass, STORAGE_VERSION, STORAGE_MIGRATION_KEY)
            if migrate_legacy
            else None
        )
        self._config_entry_id = config_entry_id

    async def async_load(self) -> dict[str, Any] | None:
        """Load pass data and copy the pre-0.4 single-instance store once."""
        data = await self._store.async_load()
        if (
            data is not None
            or self._legacy_store is None
            or self._migration_store is None
        ):
            return data

        migration = await self._migration_store.async_load()
        if migration is not None:
            return None
        legacy_data = await self._legacy_store.async_load()
        if legacy_data is not None:
            await self._store.async_save(legacy_data)
            await self._migration_store.async_save(
                {"migrated_to": self._config_entry_id}
            )
        return legacy_data

    async def async_save(self, data: dict[str, Any]) -> None:
        """Persist pass data."""
        await self._store.async_save(data)
