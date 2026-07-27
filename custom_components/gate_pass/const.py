"""Constants for Gate Pass HA."""

from typing import Final

DOMAIN: Final = "gate_pass"

CONF_ACCESS_NAME: Final = "access_name"
CONF_ACTION_LABEL: Final = "action_label"
CONF_ENTITY_ID: Final = "entity_id"
CONF_SERVICE: Final = "service"
CONF_GUEST_PORT: Final = "guest_port"
CONF_PUBLIC_BASE_URL: Final = "public_base_url"
CONF_LINK_CREATOR_USER_IDS: Final = "link_creator_user_ids"
# Kept as a read-only fallback for configurations created before 0.4.0-beta.2.
CONF_NOTIFICATION_SERVICE: Final = "notification_service"
CONF_NOTIFICATION_SERVICES: Final = "notification_services"
CONF_NOTIFICATION_EVENTS: Final = "notification_events"
CONF_DEFAULT_DURATION_HOURS: Final = "default_duration_hours"
CONF_DEFAULT_MAX_USES: Final = "default_max_uses"

DEFAULT_ACCESS_NAME: Final = "Garage gate"
DEFAULT_ACTION_LABEL: Final = "Open gate"
DEFAULT_SERVICE: Final = "button.press"
DEFAULT_GUEST_PORT: Final = 8922
DEFAULT_DURATION_HOURS: Final = 1.0
DEFAULT_MAX_USES: Final = 1
DEFAULT_NOTIFICATION_EVENTS: Final = ["used"]
NOTIFICATION_EVENTS: Final = ("created", "used", "revoked")

SERVICE_CREATE_PASS: Final = "create_pass"
SERVICE_LIST_ACCESS_POINTS: Final = "list_access_points"
SERVICE_LIST_PASSES: Final = "list_passes"
SERVICE_LIST_ACTIVITY: Final = "list_activity"
SERVICE_EXPORT_ACTIVITY: Final = "export_activity"
SERVICE_CLEAR_ACTIVITY: Final = "clear_activity"
SERVICE_REVOKE_PASS: Final = "revoke_pass"
SERVICE_REVOKE_ALL: Final = "revoke_all"

ATTR_LABEL: Final = "label"
ATTR_DURATION_HOURS: Final = "duration_hours"
ATTR_MAX_USES: Final = "max_uses"
ATTR_VALID_FROM: Final = "valid_from"
ATTR_PASS_ID: Final = "pass_id"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"

EVENT_PASS_CREATED: Final = "gate_pass_created"
EVENT_PASS_REVOKED: Final = "gate_pass_revoked"
EVENT_PASS_USED: Final = "gate_pass_used"
EVENT_ACTIVITY_CLEARED: Final = "gate_pass_activity_cleared"

CARD_URL: Final = "/gate-pass/gate-pass-card.js"
STORAGE_KEY: Final = f"{DOMAIN}.passes"
STORAGE_MIGRATION_KEY: Final = f"{DOMAIN}.storage_migration"
STORAGE_VERSION: Final = 1
ACTIVITY_LIMIT: Final = 200
PLATFORMS: Final = ("sensor",)

DATA_RUNTIMES: Final = "runtimes"
DATA_SERVERS: Final = "servers"
