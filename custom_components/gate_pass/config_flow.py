"""Config flow for Gate Pass HA."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .action_detection import action_services
from .const import (
    CONF_ACCESS_NAME,
    CONF_ACTION_LABEL,
    CONF_CREATOR_ALLOW_UNLIMITED_USES,
    CONF_CREATOR_MAX_DURATION_HOURS,
    CONF_CREATOR_MAX_USES,
    CONF_DEFAULT_DURATION_HOURS,
    CONF_DEFAULT_MAX_USES,
    CONF_ENTITY_ID,
    CONF_EXPOSE_LAST_USED_LABEL,
    CONF_GUEST_PORT,
    CONF_LINK_CREATOR_USER_IDS,
    CONF_NOTIFICATION_EVENTS,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_SERVICES,
    CONF_PUBLIC_BASE_URL,
    CONF_SERVICE,
    DEFAULT_ACCESS_NAME,
    DEFAULT_ACTION_LABEL,
    DEFAULT_CREATOR_ALLOW_UNLIMITED_USES,
    DEFAULT_CREATOR_MAX_DURATION_HOURS,
    DEFAULT_CREATOR_MAX_USES,
    DEFAULT_DURATION_HOURS,
    DEFAULT_EXPOSE_LAST_USED_LABEL,
    DEFAULT_GUEST_PORT,
    DEFAULT_MAX_USES,
    DEFAULT_NOTIFICATION_EVENTS,
    DOMAIN,
)
from .validation import (
    normalize_notification_events,
    normalize_notification_services,
    normalize_public_base_url,
    normalize_service,
    service_domain,
)
from .permissions import normalize_user_ids


def _notification_service_options(
    hass: HomeAssistant, current: Mapping[str, Any]
) -> list[selector.SelectOptionDict]:
    """Build notification choices from currently registered HA services."""
    services = hass.services.async_services_for_domain("notify")
    values = {f"notify.{service}" for service in services if service != "send_message"}
    values.update(_configured_notification_services(current))

    options = []
    for service in sorted(values):
        name = service.removeprefix("notify.")
        if name.startswith("mobile_app_"):
            name = name.removeprefix("mobile_app_")
        friendly_name = name.replace("_", " ").strip().title() or service
        options.append(
            selector.SelectOptionDict(
                value=service,
                label=f"{friendly_name} ({service})",
            )
        )
    return options


def _configured_notification_services(current: Mapping[str, Any]) -> list[str]:
    """Return current services, including the pre-beta.2 single value."""
    configured = current.get(CONF_NOTIFICATION_SERVICES)
    if configured is None:
        configured = current.get(CONF_NOTIFICATION_SERVICE, "")
    if isinstance(configured, str):
        configured = [configured] if configured.strip() else []
    if not isinstance(configured, (list, tuple, set)):
        return []
    return [str(item).strip().lower() for item in configured if str(item).strip()]


def _notification_event_options(hass: HomeAssistant) -> list[selector.SelectOptionDict]:
    """Build localized lifecycle notification choices."""
    german = str(getattr(hass.config, "language", "en")).lower().startswith("de")
    labels = (
        {
            "created": "Zugang erstellt",
            "used": "Zugang verwendet",
            "revoked": "Zugang widerrufen",
        }
        if german
        else {
            "created": "Pass created",
            "used": "Pass used",
            "revoked": "Pass revoked",
        }
    )
    return [
        selector.SelectOptionDict(value=value, label=label)
        for value, label in labels.items()
    ]


def _link_creator_options(
    users: list[Any], current: Mapping[str, Any]
) -> list[selector.SelectOptionDict]:
    """Build choices for active non-administrator Home Assistant users."""
    configured = set(normalize_user_ids(current.get(CONF_LINK_CREATOR_USER_IDS, [])))
    options: list[selector.SelectOptionDict] = []
    known_ids: set[str] = set()
    for user in users:
        user_id = str(getattr(user, "id", "")).strip()
        if not user_id:
            continue
        if user_id not in configured and (
            not bool(getattr(user, "is_active", False))
            or bool(getattr(user, "system_generated", False))
            or bool(getattr(user, "is_admin", False))
        ):
            continue
        name = str(getattr(user, "name", "")).strip() or user_id
        options.append(selector.SelectOptionDict(value=user_id, label=name))
        known_ids.add(user_id)

    for user_id in configured - known_ids:
        options.append(selector.SelectOptionDict(value=user_id, label=user_id))
    return sorted(options, key=lambda item: str(item["label"]).casefold())


def _matching_action_services(
    hass: HomeAssistant, entity_id: str, *, current_service: str = ""
) -> list[str]:
    """Return currently available entity-only actions for one entity domain."""
    domain = str(entity_id).strip().lower().partition(".")[0]
    available = hass.services.async_services_for_domain(domain) if domain else {}
    return action_services(
        entity_id, available, current_service=current_service
    )


def _action_schema(services: list[str], current_service: str = "") -> vol.Schema:
    """Build an action selector limited to the selected entity domain."""
    default = current_service if current_service in services else services[0]
    return vol.Schema(
        {
            vol.Required(CONF_SERVICE, default=default): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=service, label=service)
                        for service in services
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _prepare_action_input(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    *,
    current_service: str = "",
) -> tuple[dict[str, Any], list[str]]:
    """Validate base settings and resolve or request the matching action."""
    entity_id = str(user_input.get(CONF_ENTITY_ID, "")).strip().lower()
    services = _matching_action_services(
        hass, entity_id, current_service=current_service
    )
    if not services:
        raise vol.Invalid("no_compatible_service")

    selected = current_service if current_service in services else services[0]
    prepared = _validate({**user_input, CONF_SERVICE: selected})
    if len(services) > 1:
        prepared.pop(CONF_SERVICE, None)
    return prepared, services


def _schema(
    hass: HomeAssistant,
    current: Mapping[str, Any] | None = None,
    *,
    users: list[Any] | None = None,
) -> vol.Schema:
    """Build a frontend-serializable setup/options schema."""
    current = current or {}
    entity_default = current.get(CONF_ENTITY_ID)
    entity_key = (
        vol.Required(CONF_ENTITY_ID, default=entity_default)
        if entity_default
        else vol.Required(CONF_ENTITY_ID)
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_ACCESS_NAME,
                default=current.get(CONF_ACCESS_NAME, DEFAULT_ACCESS_NAME),
            ): selector.TextSelector(),
            vol.Required(
                CONF_ACTION_LABEL,
                default=current.get(CONF_ACTION_LABEL, DEFAULT_ACTION_LABEL),
            ): selector.TextSelector(),
            entity_key: selector.EntitySelector(),
            vol.Required(
                CONF_GUEST_PORT,
                default=current.get(CONF_GUEST_PORT, DEFAULT_GUEST_PORT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1024,
                    max=65535,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_PUBLIC_BASE_URL,
                default=current.get(CONF_PUBLIC_BASE_URL, ""),
            ): selector.TextSelector(),
            vol.Optional(
                CONF_LINK_CREATOR_USER_IDS,
                default=normalize_user_ids(current.get(CONF_LINK_CREATOR_USER_IDS, [])),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_link_creator_options(users or [], current),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    multiple=True,
                )
            ),
            vol.Required(
                CONF_CREATOR_MAX_DURATION_HOURS,
                default=current.get(
                    CONF_CREATOR_MAX_DURATION_HOURS,
                    DEFAULT_CREATOR_MAX_DURATION_HOURS,
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=720,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            ),
            vol.Required(
                CONF_CREATOR_MAX_USES,
                default=current.get(
                    CONF_CREATOR_MAX_USES, DEFAULT_CREATOR_MAX_USES
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=1000,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_CREATOR_ALLOW_UNLIMITED_USES,
                default=current.get(
                    CONF_CREATOR_ALLOW_UNLIMITED_USES,
                    DEFAULT_CREATOR_ALLOW_UNLIMITED_USES,
                ),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_EXPOSE_LAST_USED_LABEL,
                default=current.get(
                    CONF_EXPOSE_LAST_USED_LABEL,
                    DEFAULT_EXPOSE_LAST_USED_LABEL,
                ),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_NOTIFICATION_SERVICES,
                default=_configured_notification_services(current),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_notification_service_options(hass, current),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    custom_value=True,
                    multiple=True,
                )
            ),
            vol.Optional(
                CONF_NOTIFICATION_EVENTS,
                default=current.get(
                    CONF_NOTIFICATION_EVENTS, DEFAULT_NOTIFICATION_EVENTS
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_notification_event_options(hass),
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_DEFAULT_DURATION_HOURS,
                default=current.get(
                    CONF_DEFAULT_DURATION_HOURS, DEFAULT_DURATION_HOURS
                ),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=720,
                    step=0.1,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            ),
            vol.Required(
                CONF_DEFAULT_MAX_USES,
                default=current.get(CONF_DEFAULT_MAX_USES, DEFAULT_MAX_USES),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=1000,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _validate(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalize and validate submitted configuration."""
    result = dict(user_input)
    result[CONF_ACCESS_NAME] = str(result[CONF_ACCESS_NAME]).strip()
    result[CONF_ACTION_LABEL] = str(result[CONF_ACTION_LABEL]).strip()
    result[CONF_ENTITY_ID] = str(result[CONF_ENTITY_ID]).strip().lower()
    result[CONF_SERVICE] = normalize_service(result[CONF_SERVICE])
    result[CONF_PUBLIC_BASE_URL] = normalize_public_base_url(
        result.get(CONF_PUBLIC_BASE_URL, "")
    )
    result[CONF_LINK_CREATOR_USER_IDS] = normalize_user_ids(
        result.get(CONF_LINK_CREATOR_USER_IDS, [])
    )
    result[CONF_CREATOR_MAX_DURATION_HOURS] = float(
        result.get(
            CONF_CREATOR_MAX_DURATION_HOURS,
            DEFAULT_CREATOR_MAX_DURATION_HOURS,
        )
    )
    result[CONF_CREATOR_MAX_USES] = int(
        result.get(CONF_CREATOR_MAX_USES, DEFAULT_CREATOR_MAX_USES)
    )
    result[CONF_CREATOR_ALLOW_UNLIMITED_USES] = (
        result.get(
            CONF_CREATOR_ALLOW_UNLIMITED_USES,
            DEFAULT_CREATOR_ALLOW_UNLIMITED_USES,
        )
        is True
    )
    result[CONF_EXPOSE_LAST_USED_LABEL] = (
        result.get(CONF_EXPOSE_LAST_USED_LABEL, DEFAULT_EXPOSE_LAST_USED_LABEL)
        is True
    )
    result[CONF_NOTIFICATION_SERVICES] = normalize_notification_services(
        result.get(CONF_NOTIFICATION_SERVICES, [])
    )
    result[CONF_NOTIFICATION_EVENTS] = normalize_notification_events(
        result.get(CONF_NOTIFICATION_EVENTS, DEFAULT_NOTIFICATION_EVENTS)
    )
    result[CONF_GUEST_PORT] = int(result[CONF_GUEST_PORT])
    result[CONF_DEFAULT_DURATION_HOURS] = float(result[CONF_DEFAULT_DURATION_HOURS])
    result[CONF_DEFAULT_MAX_USES] = int(result[CONF_DEFAULT_MAX_USES])

    if not 0.1 <= result[CONF_CREATOR_MAX_DURATION_HOURS] <= 720:
        raise vol.Invalid("invalid_config")
    if not 1 <= result[CONF_CREATOR_MAX_USES] <= 1000:
        raise vol.Invalid("invalid_config")

    entity_domain, separator, object_id = result[CONF_ENTITY_ID].partition(".")
    if (
        not separator
        or not object_id
        or entity_domain != service_domain(result[CONF_SERVICE])
    ):
        raise vol.Invalid("domain_mismatch")
    if not result[CONF_ACCESS_NAME] or not result[CONF_ACTION_LABEL]:
        raise vol.Invalid("required")
    return result


def _set_flow_error(errors: dict[str, str], err: vol.Invalid) -> None:
    """Map validation reasons to the field shown by Home Assistant."""
    reason = str(err)
    if reason == "invalid_url":
        errors[CONF_PUBLIC_BASE_URL] = "invalid_url"
    elif reason == "invalid_notification_service":
        errors[CONF_NOTIFICATION_SERVICES] = "invalid_notification_service"
    elif reason == "invalid_notification_events":
        errors[CONF_NOTIFICATION_EVENTS] = "invalid_notification_events"
    elif reason == "invalid_service":
        errors[CONF_SERVICE] = "invalid_service"
    elif reason == "domain_mismatch":
        errors[CONF_SERVICE] = "domain_mismatch"
    elif reason == "no_compatible_service":
        errors[CONF_ENTITY_ID] = "no_compatible_service"
    else:
        errors["base"] = "invalid_config"


class GatePassConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle Gate Pass HA setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create one independently configurable access point."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data, services = _prepare_action_input(self.hass, user_input)
            except vol.Invalid as err:
                _set_flow_error(errors, err)
            else:
                if len(services) > 1:
                    self._pending_data = data
                    self._action_services = services
                    self._action_default = services[0]
                    return await self.async_step_action()
                return self.async_create_entry(title=data[CONF_ACCESS_NAME], data=data)

        users = await self.hass.auth.async_get_users()
        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self.hass, user_input, users=users),
            errors=errors,
            description_placeholders={"example_url": "https://gate.example.com"},
        )

    async def async_step_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one of several safe actions for the selected entity domain."""
        pending = getattr(self, "_pending_data", None)
        services = getattr(self, "_action_services", [])
        if not isinstance(pending, dict) or not services:
            return await self.async_step_user()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                selected = normalize_service(user_input.get(CONF_SERVICE))
                if selected not in services:
                    raise vol.Invalid("invalid_service")
                data = _validate({**pending, CONF_SERVICE: selected})
            except vol.Invalid as err:
                _set_flow_error(errors, err)
            else:
                return self.async_create_entry(title=data[CONF_ACCESS_NAME], data=data)

        entity_id = str(pending[CONF_ENTITY_ID])
        return self.async_show_form(
            step_id="action",
            data_schema=_action_schema(
                services, getattr(self, "_action_default", "")
            ),
            errors=errors,
            description_placeholders={
                "entity_id": entity_id,
                "domain": entity_id.partition(".")[0],
            },
            last_step=True,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return GatePassOptionsFlow()


class GatePassOptionsFlow(OptionsFlow):
    """Edit Gate Pass settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update options and reload the integration."""
        errors: dict[str, str] = {}
        current = {**self.config_entry.data, **self.config_entry.options}
        current_service = str(current.get(CONF_SERVICE, ""))
        if user_input is not None:
            try:
                options, services = _prepare_action_input(
                    self.hass, user_input, current_service=current_service
                )
            except vol.Invalid as err:
                _set_flow_error(errors, err)
            else:
                if len(services) > 1:
                    self._pending_data = options
                    self._action_services = services
                    self._action_default = (
                        current_service if current_service in services else services[0]
                    )
                    return await self.async_step_action()
                return self.async_create_entry(title="", data=options)
            current = user_input

        users = await self.hass.auth.async_get_users()
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(self.hass, current, users=users),
            errors=errors,
            description_placeholders={"example_url": "https://gate.example.com"},
        )

    async def async_step_action(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose one of several safe actions for the selected entity domain."""
        pending = getattr(self, "_pending_data", None)
        services = getattr(self, "_action_services", [])
        if not isinstance(pending, dict) or not services:
            return await self.async_step_init()

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                selected = normalize_service(user_input.get(CONF_SERVICE))
                if selected not in services:
                    raise vol.Invalid("invalid_service")
                options = _validate({**pending, CONF_SERVICE: selected})
            except vol.Invalid as err:
                _set_flow_error(errors, err)
            else:
                return self.async_create_entry(title="", data=options)

        entity_id = str(pending[CONF_ENTITY_ID])
        return self.async_show_form(
            step_id="action",
            data_schema=_action_schema(
                services, getattr(self, "_action_default", "")
            ),
            errors=errors,
            description_placeholders={
                "entity_id": entity_id,
                "domain": entity_id.partition(".")[0],
            },
            last_step=True,
        )
