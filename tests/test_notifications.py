"""Tests for independent multi-device notifications."""

import asyncio
from types import SimpleNamespace

from custom_components.gate_pass.const import (
    CONF_ACCESS_NAME,
    CONF_NOTIFICATION_EVENTS,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_SERVICES,
)
from custom_components.gate_pass.notifications import async_send_notification


class FakeServices:
    """Record notify calls and optionally fail selected services."""

    def __init__(self, *, fail: set[str] | None = None) -> None:
        self.calls: list[str] = []
        self.fail = fail or set()

    def has_service(self, domain: str, service: str) -> bool:
        return domain == "notify" and service != "missing"

    async def async_call(
        self,
        domain: str,
        service: str,
        _data: dict[str, str],
        *,
        blocking: bool,
    ) -> None:
        assert domain == "notify"
        assert blocking
        self.calls.append(service)
        if service in self.fail:
            raise RuntimeError("notification failed")


async def test_notification_is_sent_to_every_selected_device() -> None:
    services = FakeServices()
    hass = SimpleNamespace(services=services, config=SimpleNamespace(language="de"))
    config = {
        CONF_ACCESS_NAME: "Garage",
        CONF_NOTIFICATION_SERVICES: [
            "notify.mobile_app_one",
            "notify.mobile_app_two",
        ],
        CONF_NOTIFICATION_EVENTS: ["used"],
    }

    await async_send_notification(hass, config, "used", label="Gast")

    assert services.calls == ["mobile_app_one", "mobile_app_two"]


async def test_failed_device_does_not_block_remaining_devices() -> None:
    services = FakeServices(fail={"mobile_app_one"})
    hass = SimpleNamespace(services=services, config=SimpleNamespace(language="en"))
    config = {
        CONF_ACCESS_NAME: "Garage",
        CONF_NOTIFICATION_SERVICES: [
            "notify.mobile_app_one",
            "notify.mobile_app_two",
        ],
        CONF_NOTIFICATION_EVENTS: ["created"],
    }

    await async_send_notification(hass, config, "created", label="Guest")

    assert services.calls == ["mobile_app_one", "mobile_app_two"]


async def test_legacy_single_notification_service_still_works() -> None:
    services = FakeServices()
    hass = SimpleNamespace(services=services, config=SimpleNamespace(language="en"))
    config = {
        CONF_ACCESS_NAME: "Garage",
        CONF_NOTIFICATION_SERVICE: "notify.mobile_app_legacy",
        CONF_NOTIFICATION_EVENTS: ["revoked"],
    }

    await async_send_notification(hass, config, "revoked", label="Guest")

    assert services.calls == ["mobile_app_legacy"]


async def test_multiple_notifications_run_concurrently() -> None:
    both_started = asyncio.Event()

    class ConcurrentServices(FakeServices):
        async def async_call(
            self,
            domain: str,
            service: str,
            _data: dict[str, str],
            *,
            blocking: bool,
        ) -> None:
            assert domain == "notify"
            assert blocking
            self.calls.append(service)
            if len(self.calls) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=0.5)

    services = ConcurrentServices()
    hass = SimpleNamespace(services=services, config=SimpleNamespace(language="en"))
    config = {
        CONF_ACCESS_NAME: "Garage",
        CONF_NOTIFICATION_SERVICES: ["notify.one", "notify.two"],
        CONF_NOTIFICATION_EVENTS: ["used"],
    }

    await asyncio.wait_for(
        async_send_notification(hass, config, "used", label="Guest"), timeout=1
    )

    assert services.calls == ["one", "two"]
