"""Tests for access-point scoped Home Assistant storage migration."""

from typing import Any

from custom_components.gate_pass.const import STORAGE_KEY, STORAGE_MIGRATION_KEY
from custom_components.gate_pass import storage as storage_module


class FakeStore:
    """In-memory stand-in for Home Assistant Store."""

    data: dict[str, dict[str, Any]] = {}

    def __init__(self, _hass: object, _version: int, key: str) -> None:
        self.key = key

    async def async_load(self) -> dict[str, Any] | None:
        return self.data.get(self.key)

    async def async_save(self, data: dict[str, Any]) -> None:
        self.data[self.key] = data


async def test_legacy_storage_is_copied_only_for_migration_owner(monkeypatch) -> None:
    FakeStore.data = {STORAGE_KEY: {"passes": [{"pass_id": "gp_old"}]}}
    monkeypatch.setattr(storage_module, "Store", FakeStore)

    owner = storage_module.HomeAssistantPassStorage(
        object(), "entry-owner", migrate_legacy=True
    )
    second = storage_module.HomeAssistantPassStorage(object(), "entry-second")

    assert await owner.async_load() == FakeStore.data[STORAGE_KEY]
    assert FakeStore.data[f"{STORAGE_KEY}.entry-owner"] == FakeStore.data[STORAGE_KEY]
    assert FakeStore.data[STORAGE_MIGRATION_KEY] == {"migrated_to": "entry-owner"}
    assert await second.async_load() is None


async def test_migration_marker_prevents_reassignment(monkeypatch) -> None:
    FakeStore.data = {
        STORAGE_KEY: {"passes": [{"pass_id": "gp_old"}]},
        STORAGE_MIGRATION_KEY: {"migrated_to": "removed-entry"},
    }
    monkeypatch.setattr(storage_module, "Store", FakeStore)

    replacement = storage_module.HomeAssistantPassStorage(
        object(), "entry-replacement", migrate_legacy=True
    )

    assert await replacement.async_load() is None
    assert f"{STORAGE_KEY}.entry-replacement" not in FakeStore.data
