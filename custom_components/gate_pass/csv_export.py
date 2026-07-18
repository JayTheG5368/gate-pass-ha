"""Privacy-conscious CSV export helpers."""

from __future__ import annotations

from typing import Any


def csv_safe_activity(item: dict[str, Any]) -> dict[str, Any]:
    """Prevent spreadsheet formula execution from user-provided labels."""
    row = dict(item)
    label = str(row.get("label", ""))
    if label.startswith(("=", "+", "-", "@", "\t", "\r")):
        row["label"] = f"'{label}"
    return row
