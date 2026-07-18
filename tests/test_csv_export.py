"""Tests for privacy-conscious activity CSV values."""

from custom_components.gate_pass.csv_export import csv_safe_activity


def test_csv_labels_cannot_execute_spreadsheet_formulas() -> None:
    item = {"event_type": "created", "label": '=HYPERLINK("bad")'}

    assert csv_safe_activity(item)["label"] == '\'=HYPERLINK("bad")'
    assert item["label"] == '=HYPERLINK("bad")'
