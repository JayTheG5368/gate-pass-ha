"""Validation helpers for Gate Pass HA."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

import voluptuous as vol

from .const import DEFAULT_NOTIFICATION_EVENTS, NOTIFICATION_EVENTS

_SERVICE_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


def normalize_public_base_url(value: Any) -> str:
    """Validate and normalize an optional HTTP(S) public base URL."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise vol.Invalid("invalid_url")

    value = value.strip()
    if not value:
        return ""

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as err:
        raise vol.Invalid("invalid_url") from err

    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in value)
    ):
        raise vol.Invalid("invalid_url")

    return value.rstrip("/")


def normalize_service(value: Any) -> str:
    """Validate and normalize a Home Assistant domain.service value."""
    if not isinstance(value, str):
        raise vol.Invalid("invalid_service")
    value = value.strip().lower()
    if not _SERVICE_PATTERN.fullmatch(value):
        raise vol.Invalid("invalid_service")
    return value


def normalize_notification_service(value: Any) -> str:
    """Validate an optional classic Home Assistant notify service."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise vol.Invalid("invalid_notification_service")
    value = value.strip().lower()
    if not value:
        return ""
    if (
        not _SERVICE_PATTERN.fullmatch(value)
        or not value.startswith("notify.")
        or value == "notify.send_message"
    ):
        raise vol.Invalid("invalid_notification_service")
    return value


def normalize_notification_events(value: Any) -> list[str]:
    """Validate and normalize optional notification event selections."""
    if value is None:
        return list(DEFAULT_NOTIFICATION_EVENTS)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        raise vol.Invalid("invalid_notification_events")

    normalized = list(dict.fromkeys(str(item).strip().lower() for item in value))
    if any(item not in NOTIFICATION_EVENTS for item in normalized):
        raise vol.Invalid("invalid_notification_events")
    return normalized


def service_domain(service: str) -> str:
    """Return the domain part of a validated service name."""
    return service.partition(".")[0]
