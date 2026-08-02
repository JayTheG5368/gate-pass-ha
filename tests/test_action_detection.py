"""Tests for entity-domain action detection."""

from custom_components.gate_pass.action_detection import action_services


def test_button_action_is_detected_automatically() -> None:
    assert action_services(
        "button.garage_open", ["press", "irrelevant_service"]
    ) == ["button.press"]


def test_ambiguous_switch_actions_keep_recommended_order() -> None:
    assert action_services(
        "switch.garage",
        ["toggle", "turn_off", "set_value", "turn_on"],
    ) == ["switch.turn_on", "switch.turn_off", "switch.toggle"]


def test_existing_manual_action_remains_available() -> None:
    assert action_services(
        "cover.garage",
        ["open_cover", "close_cover"],
        current_service="cover.custom_pulse",
    ) == [
        "cover.open_cover",
        "cover.close_cover",
        "cover.custom_pulse",
    ]


def test_unknown_domain_uses_its_registered_services() -> None:
    assert action_services("custom.entry", ["activate", "deactivate"]) == [
        "custom.activate",
        "custom.deactivate",
    ]


def test_invalid_entity_has_no_actions() -> None:
    assert action_services("not-an-entity", ["turn_on"]) == []
