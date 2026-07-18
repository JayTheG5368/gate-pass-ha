"""Tests for Gate Pass configuration validation."""

import pytest
import voluptuous as vol

from custom_components.gate_pass.validation import (
    normalize_notification_service,
    normalize_public_base_url,
    normalize_service,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        (" https://gate.example.com/ ", "https://gate.example.com"),
        ("http://homeassistant.local:8922", "http://homeassistant.local:8922"),
    ],
)
def test_normalize_public_base_url(value: str, expected: str) -> None:
    assert normalize_public_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "gate.example.com",
        "ftp://gate.example.com",
        "https://user:password@gate.example.com",
        "https://gate.example.com/prefix",
        "https://gate.example.com?token=value",
    ],
)
def test_reject_invalid_public_base_url(value: str) -> None:
    with pytest.raises(vol.Invalid):
        normalize_public_base_url(value)


def test_normalize_service() -> None:
    assert normalize_service(" Button.Press ") == "button.press"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        (None, ""),
        (" Notify.Mobile_App_Phone ", "notify.mobile_app_phone"),
    ],
)
def test_normalize_notification_service(value: str | None, expected: str) -> None:
    assert normalize_notification_service(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "mobile_app_phone",
        "persistent_notification.create",
        "notify",
        "notify.send_message",
    ],
)
def test_reject_invalid_notification_service(value: str) -> None:
    with pytest.raises(vol.Invalid, match="invalid_notification_service"):
        normalize_notification_service(value)


@pytest.mark.parametrize("value", ["button", "button/press", "button.press.now"])
def test_reject_invalid_service(value: str) -> None:
    with pytest.raises(vol.Invalid):
        normalize_service(value)
