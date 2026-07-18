"""Constants for Gate Pass HA."""

from typing import Final

DOMAIN: Final = "gate_pass"

CONF_ACCESS_NAME: Final = "access_name"
CONF_ACTION_LABEL: Final = "action_label"
CONF_ENTITY_ID: Final = "entity_id"
CONF_SERVICE: Final = "service"
CONF_GUEST_PORT: Final = "guest_port"
CONF_PUBLIC_BASE_URL: Final = "public_base_url"
CONF_DEFAULT_DURATION_HOURS: Final = "default_duration_hours"
CONF_DEFAULT_MAX_USES: Final = "default_max_uses"

DEFAULT_ACCESS_NAME: Final = "Garage gate"
DEFAULT_ACTION_LABEL: Final = "Open gate"
DEFAULT_SERVICE: Final = "button.press"
DEFAULT_GUEST_PORT: Final = 8922
DEFAULT_DURATION_HOURS: Final = 1.0
DEFAULT_MAX_USES: Final = 1

SERVICE_CREATE_PASS: Final = "create_pass"
SERVICE_LIST_PASSES: Final = "list_passes"
SERVICE_REVOKE_PASS: Final = "revoke_pass"
SERVICE_REVOKE_ALL: Final = "revoke_all"

ATTR_LABEL: Final = "label"
ATTR_DURATION_HOURS: Final = "duration_hours"
ATTR_MAX_USES: Final = "max_uses"
ATTR_VALID_FROM: Final = "valid_from"
ATTR_PASS_ID: Final = "pass_id"

EVENT_PASS_CREATED: Final = "gate_pass_created"
EVENT_PASS_REVOKED: Final = "gate_pass_revoked"
EVENT_PASS_USED: Final = "gate_pass_used"

CARD_URL: Final = "/gate-pass/gate-pass-card.js"
STORAGE_KEY: Final = f"{DOMAIN}.passes"
STORAGE_VERSION: Final = 1
