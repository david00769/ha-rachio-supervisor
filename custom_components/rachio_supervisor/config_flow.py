"""Config flow for Rachio Supervisor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ALLOW_MOISTURE_WRITE_BACK,
    CONF_OBSERVE_FIRST,
    CONF_RACHIO_CONFIG_ENTRY_ID,
    CONF_RAIN_ACTUALS_ENTITY,
    CONF_SITE_NAME,
    CONF_ZONE_COUNT,
    DEFAULT_ALLOW_MOISTURE_WRITE_BACK,
    DEFAULT_OBSERVE_FIRST,
    DEFAULT_ZONE_COUNT,
    DOMAIN,
)
from .discovery import rachio_entry_options


def _flow_schema(
    rachio_options: list[tuple[str, str]],
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the shared config form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_SITE_NAME,
                default=defaults.get(CONF_SITE_NAME, "Rachio Site"),
            ): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(
                CONF_RACHIO_CONFIG_ENTRY_ID,
                default=defaults.get(
                    CONF_RACHIO_CONFIG_ENTRY_ID,
                    rachio_options[0][0] if rachio_options else "",
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=value, label=label)
                        for value, label in rachio_options
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_RAIN_ACTUALS_ENTITY,
                default=defaults.get(CONF_RAIN_ACTUALS_ENTITY, ""),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=False)
            ),
            vol.Required(
                CONF_ZONE_COUNT,
                default=defaults.get(CONF_ZONE_COUNT, DEFAULT_ZONE_COUNT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=32, step=1, mode=selector.NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_OBSERVE_FIRST,
                default=defaults.get(CONF_OBSERVE_FIRST, DEFAULT_OBSERVE_FIRST),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_ALLOW_MOISTURE_WRITE_BACK,
                default=defaults.get(
                    CONF_ALLOW_MOISTURE_WRITE_BACK,
                    DEFAULT_ALLOW_MOISTURE_WRITE_BACK,
                ),
            ): selector.BooleanSelector(),
        }
    )


class RachioSupervisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rachio Supervisor."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        options = rachio_entry_options(self.hass)
        if not options:
            return self.async_abort(reason="no_rachio_entries")

        if user_input is not None:
            unique_id = user_input[CONF_RACHIO_CONFIG_ENTRY_ID].strip() or slugify(
                user_input[CONF_SITE_NAME]
            )
            await self.async_set_unique_id(f"rachio_supervisor::{unique_id}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_SITE_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=_flow_schema(options),
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow handler."""
        return RachioSupervisorOptionsFlow(config_entry)


class RachioSupervisorOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Rachio Supervisor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {**self.config_entry.data, **self.config_entry.options}
        options = rachio_entry_options(self.hass)
        return self.async_show_form(
            step_id="init",
            data_schema=_flow_schema(options, defaults),
        )
