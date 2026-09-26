"""Permission helpers for Gate Pass management actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_CREATOR_ALLOW_UNLIMITED_USES,
    CONF_CREATOR_MAX_DURATION_HOURS,
    CONF_CREATOR_MAX_USES,
    CONF_LINK_CREATOR_USER_IDS,
    DEFAULT_CREATOR_ALLOW_UNLIMITED_USES,
    DEFAULT_CREATOR_MAX_DURATION_HOURS,
    DEFAULT_CREATOR_MAX_USES,
    MAX_DURATION_HOURS,
    MAX_USES,
)


@dataclass(frozen=True)
class AccessRights:
    """Capabilities for one caller and access point."""

    can_create: bool
    can_manage: bool
    owner_user_id: str | None

    @property
    def can_revoke(self) -> bool:
        """Return whether the caller may revoke passes visible to them."""
        return self.can_create or self.can_manage

    def as_dict(self) -> dict[str, bool]:
        """Return frontend-safe capability flags."""
        return {
            "can_create": self.can_create,
            "can_manage": self.can_manage,
            "can_revoke": self.can_revoke,
        }


NO_ACCESS = AccessRights(False, False, None)
FULL_ACCESS = AccessRights(True, True, None)


@dataclass(frozen=True)
class CreationLimits:
    """Pass creation limits exposed to an authorized caller."""

    max_duration_hours: float
    max_uses: int
    allow_unlimited_uses: bool
    restricted: bool

    def as_dict(self) -> dict[str, bool | float | int]:
        """Return frontend-safe creation limits."""
        return {
            "max_duration_hours": self.max_duration_hours,
            "max_uses": self.max_uses,
            "allow_unlimited_uses": self.allow_unlimited_uses,
            "restricted": self.restricted,
        }


def normalize_user_ids(value: Any) -> list[str]:
    """Normalize a selector value to unique non-empty user IDs."""
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        return []

    normalized: list[str] = []
    for item in values:
        user_id = str(item).strip()
        if user_id and user_id not in normalized:
            normalized.append(user_id)
    return normalized


def access_rights(
    config: Mapping[str, Any], user_id: str | None, *, is_admin: bool
) -> AccessRights:
    """Return rights for one caller without exposing configured user IDs."""
    if user_id is None or is_admin:
        return FULL_ACCESS
    if user_id in normalize_user_ids(config.get(CONF_LINK_CREATOR_USER_IDS, [])):
        return AccessRights(True, False, user_id)
    return NO_ACCESS


def creation_limits(config: Mapping[str, Any], *, is_admin: bool) -> CreationLimits:
    """Return configured limits, leaving administrators unrestricted."""
    if is_admin:
        return CreationLimits(MAX_DURATION_HOURS, MAX_USES, True, False)
    return CreationLimits(
        max_duration_hours=float(
            config.get(
                CONF_CREATOR_MAX_DURATION_HOURS,
                DEFAULT_CREATOR_MAX_DURATION_HOURS,
            )
        ),
        max_uses=int(config.get(CONF_CREATOR_MAX_USES, DEFAULT_CREATOR_MAX_USES)),
        allow_unlimited_uses=bool(
            config.get(
                CONF_CREATOR_ALLOW_UNLIMITED_USES,
                DEFAULT_CREATOR_ALLOW_UNLIMITED_USES,
            )
        ),
        restricted=True,
    )


def validate_creation_request(
    limits: CreationLimits, *, duration_hours: float, max_uses: int
) -> None:
    """Reject pass settings outside the caller's configured limits."""
    if duration_hours > limits.max_duration_hours:
        raise ValueError(
            f"Validity exceeds the allowed maximum of {limits.max_duration_hours:g} hours"
        )
    if max_uses == 0 and not limits.allow_unlimited_uses:
        raise ValueError("Unlimited use is not allowed for this link creator")
    if max_uses > limits.max_uses:
        raise ValueError(f"Use limit exceeds the allowed maximum of {limits.max_uses}")
