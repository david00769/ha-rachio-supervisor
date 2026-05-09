"""Config flow for Rachio Supervisor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ALLOW_MOISTURE_WRITE_BACK,
    CONF_AUTO_CATCH_UP_SCHEDULES,
    CONF_MOISTURE_SENSOR_ENTITIES,
    CONF_OBSERVE_FIRST,
    CONF_RACHIO_CONFIG_ENTRY_ID,
    CONF_RAIN_ACTUALS_ENTITY,
    CONF_SCHEDULE_MOISTURE_MAP,
    CONF_SITE_NAME,
    CONF_ZONE_COUNT,
    DEFAULT_ALLOW_MOISTURE_WRITE_BACK,
    DEFAULT_AUTO_CATCH_UP_SCHEDULES,
    DEFAULT_MOISTURE_SENSOR_ENTITIES,
    DEFAULT_SCHEDULE_MOISTURE_MAP,
    DEFAULT_OBSERVE_FIRST,
    DEFAULT_ZONE_COUNT,
    DOMAIN,
)
from .discovery import rachio_entry_options, schedule_entity_options

UNMAPPED_SENTINEL = "__unmapped__"


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
            vol.Required(
                CONF_MOISTURE_SENSOR_ENTITIES,
                default=defaults.get(
                    CONF_MOISTURE_SENSOR_ENTITIES,
                    DEFAULT_MOISTURE_SENSOR_ENTITIES,
                ),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", multiple=True)
            ),
        }
    )


def _policy_schema(
    schedule_options: list[tuple[str, str]],
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the schedule policy schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_AUTO_CATCH_UP_SCHEDULES,
                default=defaults.get(
                    CONF_AUTO_CATCH_UP_SCHEDULES,
                    DEFAULT_AUTO_CATCH_UP_SCHEDULES,
                ),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=value, label=label)
                        for value, label in schedule_options
                    ],
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            ),
        }
    )


class RachioSupervisorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rachio Supervisor."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        self._basic_input: dict[str, Any] = {}
        self._policy_input: dict[str, Any] = {}
        self._schedule_options: list[tuple[str, str]] = []
        self._moisture_mapping: dict[str, str] = {}
        self._mapping_index = 0

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        options = rachio_entry_options(self.hass)
        if not options:
            return self.async_abort(reason="no_rachio_entries")

        if user_input is not None:
            self._basic_input = dict(user_input)
            return await self.async_step_policy()

        return self.async_show_form(
            step_id="user",
            data_schema=_flow_schema(options),
        )

    async def async_step_policy(self, user_input: dict[str, Any] | None = None):
        """Handle per-schedule policy configuration."""
        selected_entry_id = self._basic_input[CONF_RACHIO_CONFIG_ENTRY_ID]
        self._schedule_options = schedule_entity_options(self.hass, selected_entry_id)

        if user_input is not None:
            self._policy_input = {
                CONF_AUTO_CATCH_UP_SCHEDULES: user_input.get(
                    CONF_AUTO_CATCH_UP_SCHEDULES,
                    [],
                )
            }
            self._moisture_mapping = {}
            self._mapping_index = 0
            return await self.async_step_moisture_map()

        return self.async_show_form(
            step_id="policy",
            data_schema=_policy_schema(self._schedule_options),
        )

    async def async_step_moisture_map(self, user_input: dict[str, Any] | None = None):
        """Map candidate moisture sensors to schedules explicitly."""
        moisture_candidates = [
            entity_id
            for entity_id in self._basic_input.get(CONF_MOISTURE_SENSOR_ENTITIES, [])
            if isinstance(entity_id, str)
        ]
        if not self._schedule_options:
            final_input = {
                **self._basic_input,
                **self._policy_input,
                CONF_SCHEDULE_MOISTURE_MAP: DEFAULT_SCHEDULE_MOISTURE_MAP,
            }
            unique_id = final_input[CONF_RACHIO_CONFIG_ENTRY_ID].strip() or slugify(
                final_input[CONF_SITE_NAME]
            )
            await self.async_set_unique_id(f"rachio_supervisor::{unique_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=final_input[CONF_SITE_NAME],
                data=final_input,
            )

        if self._mapping_index >= len(self._schedule_options):
            final_input = {
                **self._basic_input,
                **self._policy_input,
                CONF_SCHEDULE_MOISTURE_MAP: self._moisture_mapping,
            }
            unique_id = final_input[CONF_RACHIO_CONFIG_ENTRY_ID].strip() or slugify(
                final_input[CONF_SITE_NAME]
            )
            await self.async_set_unique_id(f"rachio_supervisor::{unique_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=final_input[CONF_SITE_NAME],
                data=final_input,
            )

        schedule_entity_id, schedule_label = self._schedule_options[self._mapping_index]
        field_key = "moisture_entity"
        if user_input is not None:
            selected = str(user_input.get(field_key, UNMAPPED_SENTINEL))
            if selected != UNMAPPED_SENTINEL:
                self._moisture_mapping[schedule_entity_id] = selected
            self._mapping_index += 1
            return await self.async_step_moisture_map()

        options = [selector.SelectOptionDict(value=UNMAPPED_SENTINEL, label="Unmapped")]
        for entity_id in moisture_candidates:
            state = self.hass.states.get(entity_id)
            label = str(state.attributes.get("friendly_name")) if state else entity_id
            options.append(selector.SelectOptionDict(value=entity_id, label=label))

        schema = vol.Schema(
            {
                vol.Required(field_key, default=UNMAPPED_SENTINEL): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="moisture_map",
            description_placeholders={
                "schedule_name": schedule_label,
                "position": str(self._mapping_index + 1),
                "total": str(len(self._schedule_options)),
            },
            data_schema=schema,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow handler."""
        return RachioSupervisorOptionsFlow(config_entry)


class RachioSupervisorOptionsFlow(config_entries.OptionsFlow):
    """Handle options for Rachio Supervisor."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._basic_input: dict[str, Any] = {}
        self._policy_input: dict[str, Any] = {}
        self._schedule_options: list[tuple[str, str]] = []
        self._moisture_mapping: dict[str, str] = {}
        self._mapping_index = 0

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the integration options."""
        if user_input is not None:
            self._basic_input = dict(user_input)
            return await self.async_step_policy()

        defaults = {**self.config_entry.data, **self.config_entry.options}
        options = rachio_entry_options(self.hass)
        return self.async_show_form(
            step_id="init",
            data_schema=_flow_schema(options, defaults),
        )

    async def async_step_policy(self, user_input: dict[str, Any] | None = None):
        """Manage schedule policy options."""
        defaults = {**self.config_entry.data, **self.config_entry.options}
        selected_entry_id = self._basic_input.get(
            CONF_RACHIO_CONFIG_ENTRY_ID,
            defaults.get(CONF_RACHIO_CONFIG_ENTRY_ID, ""),
        )
        self._schedule_options = schedule_entity_options(self.hass, selected_entry_id)

        if user_input is not None:
            self._policy_input = {
                CONF_AUTO_CATCH_UP_SCHEDULES: user_input.get(
                    CONF_AUTO_CATCH_UP_SCHEDULES,
                    [],
                )
            }
            self._moisture_mapping = {}
            self._mapping_index = 0
            return await self.async_step_moisture_map()

        return self.async_show_form(
            step_id="policy",
            data_schema=_policy_schema(self._schedule_options, defaults),
        )

    async def async_step_moisture_map(self, user_input: dict[str, Any] | None = None):
        """Manage explicit schedule-to-moisture mapping options."""
        defaults = {**self.config_entry.data, **self.config_entry.options}
        moisture_candidates = [
            entity_id
            for entity_id in self._basic_input.get(
                CONF_MOISTURE_SENSOR_ENTITIES,
                defaults.get(CONF_MOISTURE_SENSOR_ENTITIES, []),
            )
            if isinstance(entity_id, str)
        ]
        existing_map = defaults.get(CONF_SCHEDULE_MOISTURE_MAP, DEFAULT_SCHEDULE_MOISTURE_MAP)

        if not self._schedule_options:
            return self.async_create_entry(
                title="",
                data={
                    **self._basic_input,
                    **self._policy_input,
                    CONF_SCHEDULE_MOISTURE_MAP: DEFAULT_SCHEDULE_MOISTURE_MAP,
                },
            )

        if self._mapping_index >= len(self._schedule_options):
            return self.async_create_entry(
                title="",
                data={
                    **self._basic_input,
                    **self._policy_input,
                    CONF_SCHEDULE_MOISTURE_MAP: self._moisture_mapping,
                },
            )

        schedule_entity_id, schedule_label = self._schedule_options[self._mapping_index]
        field_key = "moisture_entity"
        if user_input is not None:
            selected = str(user_input.get(field_key, UNMAPPED_SENTINEL))
            if selected != UNMAPPED_SENTINEL:
                self._moisture_mapping[schedule_entity_id] = selected
            self._mapping_index += 1
            return await self.async_step_moisture_map()

        default_value = existing_map.get(schedule_entity_id, UNMAPPED_SENTINEL)
        options = [selector.SelectOptionDict(value=UNMAPPED_SENTINEL, label="Unmapped")]
        for entity_id in moisture_candidates:
            state = self.hass.states.get(entity_id)
            label = str(state.attributes.get("friendly_name")) if state else entity_id
            options.append(selector.SelectOptionDict(value=entity_id, label=label))
        schema = vol.Schema(
            {
                vol.Required(field_key, default=default_value): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )
        return self.async_show_form(
            step_id="moisture_map",
            description_placeholders={
                "schedule_name": schedule_label,
                "position": str(self._mapping_index + 1),
                "total": str(len(self._schedule_options)),
            },
            data_schema=schema,
        )
