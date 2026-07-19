"""Tests for multi-access guest URL generation and dispatch."""

from types import SimpleNamespace

from custom_components.gate_pass.const import (
    CONF_ACCESS_NAME,
    CONF_PUBLIC_BASE_URL,
)
from custom_components.gate_pass.server import (
    BRAND_ICON_PATH,
    GUEST_PAGE_HTML,
    GuestServer,
)


def _config(name: str, public_url: str = "") -> dict[str, str]:
    return {CONF_ACCESS_NAME: name, CONF_PUBLIC_BASE_URL: public_url}


def test_guest_page_uses_bundled_brand_icon() -> None:
    assert BRAND_ICON_PATH.is_file()
    assert 'src="/gate-pass/assets/icon.png"' in GUEST_PAGE_HTML
    assert "&#x25A3;" not in GUEST_PAGE_HTML


def test_shared_server_builds_separate_scoped_public_urls() -> None:
    hass = SimpleNamespace(
        config=SimpleNamespace(
            internal_url="http://homeassistant.local:8123", external_url=None
        )
    )
    server = GuestServer(hass, 8922)
    server.register("entry-one", object(), _config("Garage", "https://gate.test"))
    server.register("entry-two", object(), _config("Side door", "https://door.test"))

    assert server.build_guest_url("entry-one", "gp_one", "secret-one") == (
        "https://gate.test/gate-pass/guest/entry-one/gp_one/secret-one"
    )
    assert server.build_guest_url("entry-two", "gp_two", "secret-two") == (
        "https://door.test/gate-pass/guest/entry-two/gp_two/secret-two"
    )


def test_automatic_url_keeps_local_host_and_shared_port() -> None:
    hass = SimpleNamespace(
        config=SimpleNamespace(
            internal_url="http://homeassistant.local:8123", external_url=None
        )
    )
    server = GuestServer(hass, 8922)
    server.register("entry-one", object(), _config("Garage"))

    assert server.build_guest_url("entry-one", "gp_one", "secret") == (
        "http://homeassistant.local:8922/gate-pass/guest/entry-one/gp_one/secret"
    )


def test_legacy_route_is_bound_only_to_legacy_owner() -> None:
    hass = SimpleNamespace(config=SimpleNamespace(internal_url=None, external_url=None))
    server = GuestServer(hass, 8922)
    server.register("entry-one", object(), _config("Garage"), legacy=True)
    server.register("entry-two", object(), _config("Side door"))

    target = server._resolve_access_point(SimpleNamespace(match_info={}))
    assert target is not None
    assert target.entry_id == "entry-one"
    scoped = server._resolve_access_point(
        SimpleNamespace(match_info={"entry_id": "entry-two"})
    )
    assert scoped is not None
    assert scoped.entry_id == "entry-two"


def test_browser_origin_accepts_same_host_and_non_browser_requests() -> None:
    assert GuestServer._check_browser_origin(SimpleNamespace(headers={}))
    assert GuestServer._check_browser_origin(
        SimpleNamespace(
            headers={
                "Origin": "https://gate.test",
                "Host": "gate.test",
                "Sec-Fetch-Site": "same-origin",
            }
        )
    )
    assert GuestServer._check_browser_origin(
        SimpleNamespace(headers={"Origin": "http://[::1]:8922", "Host": "[::1]:8922"})
    )


def test_browser_origin_rejects_cross_site_and_malformed_origins() -> None:
    rejected_headers = (
        {"Sec-Fetch-Site": "cross-site"},
        {"Origin": "null", "Host": "gate.test"},
        {"Origin": "not-a-url", "Host": "gate.test"},
        {"Origin": "ftp://gate.test", "Host": "gate.test"},
        {"Origin": "https://evil.test", "Host": "gate.test"},
        {"Origin": "https://gate.test", "Host": ""},
    )
    for headers in rejected_headers:
        assert not GuestServer._check_browser_origin(SimpleNamespace(headers=headers))
