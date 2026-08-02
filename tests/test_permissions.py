"""Tests for Gate Pass permission helpers."""

import pytest

from custom_components.gate_pass.const import (
    CONF_CREATOR_ALLOW_UNLIMITED_USES,
    CONF_CREATOR_MAX_DURATION_HOURS,
    CONF_CREATOR_MAX_USES,
    CONF_LINK_CREATOR_USER_IDS,
)
from custom_components.gate_pass.permissions import (
    access_rights,
    creation_limits,
    normalize_user_ids,
    validate_creation_request,
)


def test_normalize_user_ids_removes_blanks_and_duplicates() -> None:
    assert normalize_user_ids([" alice ", "", "alice", "bob"]) == [
        "alice",
        "bob",
    ]
    assert normalize_user_ids("alice") == ["alice"]
    assert normalize_user_ids(None) == []


def test_access_rights_are_scoped_to_configured_creators() -> None:
    config = {CONF_LINK_CREATOR_USER_IDS: ["alice"]}

    creator = access_rights(config, "alice", is_admin=False)
    denied = access_rights(config, "bob", is_admin=False)
    admin = access_rights(config, "admin", is_admin=True)
    internal = access_rights(config, None, is_admin=False)

    assert creator.can_create and creator.can_revoke
    assert not creator.can_manage
    assert creator.owner_user_id == "alice"
    assert not denied.can_create and not denied.can_manage
    assert admin.can_manage and admin.owner_user_id is None
    assert internal.can_manage and internal.owner_user_id is None


def test_creation_limits_apply_only_to_non_administrators() -> None:
    config = {
        CONF_CREATOR_MAX_DURATION_HOURS: 12,
        CONF_CREATOR_MAX_USES: 3,
        CONF_CREATOR_ALLOW_UNLIMITED_USES: False,
    }

    creator = creation_limits(config, is_admin=False)
    admin = creation_limits(config, is_admin=True)

    assert creator.as_dict() == {
        "max_duration_hours": 12.0,
        "max_uses": 3,
        "allow_unlimited_uses": False,
        "restricted": True,
    }
    assert admin.max_duration_hours == 720
    assert admin.max_uses == 1000
    assert admin.allow_unlimited_uses
    assert not admin.restricted


def test_creation_request_rejects_every_configured_limit() -> None:
    limits = creation_limits(
        {
            CONF_CREATOR_MAX_DURATION_HOURS: 12,
            CONF_CREATOR_MAX_USES: 3,
            CONF_CREATOR_ALLOW_UNLIMITED_USES: False,
        },
        is_admin=False,
    )

    validate_creation_request(limits, duration_hours=12, max_uses=3)
    with pytest.raises(ValueError, match="Validity exceeds"):
        validate_creation_request(limits, duration_hours=12.1, max_uses=1)
    with pytest.raises(ValueError, match="Unlimited use"):
        validate_creation_request(limits, duration_hours=1, max_uses=0)
    with pytest.raises(ValueError, match="Use limit exceeds"):
        validate_creation_request(limits, duration_hours=1, max_uses=4)
