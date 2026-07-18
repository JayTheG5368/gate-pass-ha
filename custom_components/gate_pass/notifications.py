"""Optional administrator-configured Gate Pass notifications."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    CONF_ACCESS_NAME,
    CONF_NOTIFICATION_EVENTS,
    CONF_NOTIFICATION_SERVICE,
    DEFAULT_NOTIFICATION_EVENTS,
)

_LOGGER = logging.getLogger(__name__)


async def async_send_notification(
    hass: HomeAssistant,
    config: dict[str, Any],
    event_type: str,
    *,
    label: str = "",
    count: int | None = None,
) -> None:
    """Send one configured lifecycle notification without affecting pass actions."""
    notification_service = str(config.get(CONF_NOTIFICATION_SERVICE, "")).strip()
    enabled_events = config.get(CONF_NOTIFICATION_EVENTS, DEFAULT_NOTIFICATION_EVENTS)
    if not notification_service or event_type not in enabled_events:
        return

    domain, _, service = notification_service.partition(".")
    if not hass.services.has_service(domain, service):
        _LOGGER.warning(
            "Gate Pass notification service %s is unavailable",
            notification_service,
        )
        return

    access_name = str(config[CONF_ACCESS_NAME])
    german = str(getattr(hass.config, "language", "en")).lower().startswith("de")
    if event_type == "created":
        message = (
            f'Zugang "{label}" wurde erstellt.'
            if german
            else f'Pass "{label}" was created.'
        )
    elif event_type == "revoked" and count is not None:
        message = (
            f"{count} Zugang/Zugänge wurden widerrufen."
            if german
            else f"{count} pass(es) were revoked."
        )
    elif event_type == "revoked":
        message = (
            f'Zugang "{label}" wurde widerrufen.'
            if german
            else f'Pass "{label}" was revoked.'
        )
    else:
        message = (
            f'"{label}" hat den Zugang erfolgreich verwendet.'
            if german
            else f'"{label}" successfully used the access link.'
        )

    try:
        await hass.services.async_call(
            domain,
            service,
            {"title": f"Gate Pass: {access_name}", "message": message},
            blocking=True,
        )
    except Exception:
        _LOGGER.exception("Gate Pass %s notification failed", event_type)
