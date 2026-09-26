"""Test configuration for Gate Pass HA core modules."""

import sys
from pathlib import Path
from types import ModuleType

# Load the pure core modules without importing the Home Assistant integration
# package entrypoint. Full HA wiring is exercised on the target test instance.
component_path = Path(__file__).parents[1] / "custom_components" / "gate_pass"
package = ModuleType("custom_components.gate_pass")
package.__path__ = [str(component_path)]
sys.modules["custom_components.gate_pass"] = package

# Lightweight Home Assistant import stubs for adapter and URL unit tests. The
# real integration wiring is exercised on the target Home Assistant instance.
homeassistant = ModuleType("homeassistant")
homeassistant.__path__ = []
homeassistant_core = ModuleType("homeassistant.core")
homeassistant_core.HomeAssistant = object
homeassistant_helpers = ModuleType("homeassistant.helpers")
homeassistant_helpers.__path__ = []
homeassistant_storage = ModuleType("homeassistant.helpers.storage")
homeassistant_storage.Store = object
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.core", homeassistant_core)
sys.modules.setdefault("homeassistant.helpers", homeassistant_helpers)
sys.modules.setdefault("homeassistant.helpers.storage", homeassistant_storage)
