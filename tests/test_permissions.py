"""Tests for Gate Pass permission helpers."""

from custom_components.gate_pass.const import CONF_LINK_CREATOR_USER_IDS
from custom_components.gate_pass.permissions import access_rights, normalize_user_ids


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
