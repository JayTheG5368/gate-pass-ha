"""Config flow for Gate Pass HA."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_ACCESS_NAME,
    CONF_ACTION_LABEL,
    CONF_DEFAULT_DURATION_HOURS,
    CONF_DEFAULT_MAX_USES,
    CONF_ENTITY_ID,
    CONF_GUEST_PORT,
    CONF_NOTIFICATION_EVENTS,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_SERVICES,
    CONF_PUBLIC_BASE_URL,
    CONF_SERVICE,
    DEFAULT_ACCESS_NAME,
    DEFAULT_ACTION_LABEL,
    DEFAULT_DURATION_HOURS,
    DEFAULT_GUEST_PORT,
    DEFAULT_MAX_USES,
    DEFAULT_NOTIFICATION_EVENTS,
    DEFAULT_SERVICE,
    DOMAIN,
)
from .validation import (
    normalize_notification_events,
    normalize_notification_services,
    normalize_public_base_url,
    normalize_service,
    service_domain,
)


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


def _schema(
    hass: HomeAssistant, current: Mapping[str, Any] | None = None
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
                CONF_SERVICE,
                default=current.get(CONF_SERVICE, DEFAULT_SERVICE),
            ): selector.TextSelector(),
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
    result[CONF_NOTIFICATION_SERVICES] = normalize_notification_services(
        result.get(CONF_NOTIFICATION_SERVICES, [])
    )
    result[CONF_NOTIFICATION_EVENTS] = normalize_notification_events(
        result.get(CONF_NOTIFICATION_EVENTS, DEFAULT_NOTIFICATION_EVENTS)
    )
    result[CONF_GUEST_PORT] = int(result[CONF_GUEST_PORT])
    result[CONF_DEFAULT_DURATION_HOURS] = float(result[CONF_DEFAULT_DURATION_HOURS])
    result[CONF_DEFAULT_MAX_USES] = int(result[CONF_DEFAULT_MAX_USES])

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
                data = _validate(user_input)
            except vol.Invalid as err:
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
                else:
                    errors["base"] = "invalid_config"
            else:
                return self.async_create_entry(title=data[CONF_ACCESS_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(self.hass, user_input),
            errors=errors,
            description_placeholders={"example_url": "https://gate.example.com"},
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
        if user_input is not None:
            try:
                options = _validate(user_input)
            except vol.Invalid as err:
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
                else:
                    errors["base"] = "invalid_config"
            else:
                return self.async_create_entry(title="", data=options)
            current = user_input

        return self.async_show_form(
            step_id="init",
            data_schema=_schema(self.hass, current),
            errors=errors,
            description_placeholders={"example_url": "https://gate.example.com"},
            last_step=True,
        )
