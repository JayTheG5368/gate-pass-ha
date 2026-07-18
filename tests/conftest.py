"""Test configuration for Gate Pass HA core modules."""

from pathlib import Path
import sys
from types import ModuleType


# Load the pure core modules without importing the Home Assistant integration
# package entrypoint. Full HA wiring is exercised on the target test instance.
component_path = Path(__file__).parents[1] / "custom_components" / "gate_pass"
package = ModuleType("custom_components.gate_pass")
package.__path__ = [str(component_path)]
sys.modules["custom_components.gate_pass"] = package
