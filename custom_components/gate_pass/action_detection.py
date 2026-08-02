"""Detect safe entity-only Home Assistant actions."""

from __future__ import annotations

from collections.abc import Iterable


# Every listed action can be called with only an entity_id. The first action is
# the recommended choice when a domain offers more than one useful operation.
DOMAIN_ACTIONS: dict[str, tuple[str, ...]] = {
    "automation": ("trigger",),
    "button": ("press",),
    "climate": ("turn_on", "turn_off"),
    "counter": ("increment", "decrement", "reset"),
    "cover": ("open_cover", "close_cover", "stop_cover", "toggle"),
    "event": ("trigger",),
    "fan": ("turn_on", "turn_off", "toggle"),
    "group": ("turn_on", "turn_off", "toggle"),
    "humidifier": ("turn_on", "turn_off", "toggle"),
    "input_boolean": ("turn_on", "turn_off", "toggle"),
    "input_button": ("press",),
    "input_number": ("increment", "decrement"),
    "input_select": ("select_next", "select_previous"),
    "lawn_mower": ("start_mowing", "dock", "pause"),
    "light": ("turn_on", "turn_off", "toggle"),
    "lock": ("unlock", "lock", "open"),
    "media_player": (
        "turn_on",
        "turn_off",
        "media_play_pause",
        "media_play",
        "media_pause",
        "media_stop",
    ),
    "remote": ("turn_on", "turn_off", "toggle"),
    "scene": ("turn_on",),
    "script": ("turn_on",),
    "siren": ("turn_on", "turn_off"),
    "switch": ("turn_on", "turn_off", "toggle"),
    "timer": ("start", "cancel", "pause", "finish"),
    "vacuum": ("start", "return_to_base", "stop", "pause"),
    "valve": ("open_valve", "close_valve", "stop_valve", "toggle"),
    "water_heater": ("turn_on", "turn_off"),
}


def action_services(
    entity_id: str,
    available_services: Iterable[str],
    *,
    current_service: str = "",
) -> list[str]:
    """Return matching full service names in recommended display order."""
    domain, separator, object_id = str(entity_id).strip().lower().partition(".")
    if not separator or not domain or not object_id:
        return []

    available = {str(service).strip().lower() for service in available_services}
    preferred = DOMAIN_ACTIONS.get(domain)
    if preferred is None:
        candidates = sorted(available)
    else:
        candidates = [service for service in preferred if service in available]

    current = str(current_service).strip().lower()
    current_domain, current_separator, current_action = current.partition(".")
    if (
        current_separator
        and current_domain == domain
        and current_action
        and current_action not in candidates
    ):
        candidates.append(current_action)

    return [f"{domain}.{service}" for service in candidates]
