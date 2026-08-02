"""Validate files required for publishing Gate Pass HA."""

from __future__ import annotations

import json
from pathlib import Path
import struct


ROOT = Path(__file__).parents[1]
INTEGRATION = ROOT / "custom_components" / "gate_pass"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    return struct.unpack(">II", data[16:24])


def test_release_versions_match() -> None:
    """Keep every user-visible release version synchronized."""
    manifest = _read_json(INTEGRATION / "manifest.json")
    package = _read_json(ROOT / "package.json")
    package_lock = _read_json(ROOT / "package-lock.json")

    assert manifest["version"] == package["version"]
    assert manifest["version"] == package_lock["version"]
    assert manifest["version"] == package_lock["packages"][""]["version"]
    assert f"?v={manifest['version']}" in (ROOT / "README.md").read_text(
        encoding="utf-8"
    )


def test_publish_metadata_is_complete() -> None:
    """Require the metadata used by Home Assistant and HACS."""
    manifest = _read_json(INTEGRATION / "manifest.json")
    hacs = _read_json(ROOT / "hacs.json")

    assert manifest["codeowners"] == ["@JayTheG5368"]
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].endswith("/issues")
    assert hacs == {"name": "Gate Pass HA"}
    assert not (INTEGRATION / "strings.json").exists()


def test_translations_have_matching_top_level_keys() -> None:
    """English and German must cover the same integration features."""
    english = _read_json(INTEGRATION / "translations" / "en.json")
    german = _read_json(INTEGRATION / "translations" / "de.json")

    assert english.keys() == german.keys()
    assert english["config"]["step"].keys() == german["config"]["step"].keys()
    assert english["options"]["step"].keys() == german["options"]["step"].keys()
    assert english["services"].keys() == german["services"].keys()
    assert "https://" not in json.dumps(english)
    assert "https://" not in json.dumps(german)


def test_security_options_are_translated_in_every_flow() -> None:
    """Keep creator limits and sensor privacy understandable to administrators."""
    fields = {
        "creator_max_duration_hours",
        "creator_max_uses",
        "creator_allow_unlimited_uses",
        "expose_last_used_label",
    }
    for language in ("en", "de"):
        translations = _read_json(INTEGRATION / "translations" / f"{language}.json")
        config_data = translations["config"]["step"]["user"]["data"]
        options_data = translations["options"]["step"]["init"]["data"]
        assert fields <= config_data.keys()
        assert fields <= options_data.keys()


def test_service_descriptions_translations_and_icons_match() -> None:
    """Keep every administrator action visible and translated in Home Assistant."""
    english = _read_json(INTEGRATION / "translations" / "en.json")
    icons = _read_json(INTEGRATION / "icons.json")
    services = {
        line.split(":", 1)[0]
        for line in (INTEGRATION / "services.yaml")
        .read_text(encoding="utf-8")
        .splitlines()
        if line and not line.startswith(" ") and ":" in line
    }

    assert services == set(english["services"])
    assert services == set(icons["services"])


def test_brand_icon_dimensions() -> None:
    """Ship normal and high-DPI Home Assistant brand icons."""
    brand = INTEGRATION / "brand"

    assert _png_size(brand / "icon.png") == (256, 256)
    assert _png_size(brand / "icon@2x.png") == (512, 512)
