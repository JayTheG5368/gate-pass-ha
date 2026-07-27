"""Permission helpers for Gate Pass management actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .const import CONF_LINK_CREATOR_USER_IDS


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
