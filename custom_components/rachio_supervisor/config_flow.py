"""Config flow for Rachio Supervisor."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.util import slugify

from .const import (
    CONF_ALLOW_MOISTURE_WRITE_BACK,
    CONF_AUTO_CATCH_UP_SCHEDULES,
    CONF_AUTO_MOISTURE_WRITE_SCHEDULES,
    CONF_AUTO_MISSED_RUN_SCHEDULES,
    CONF_ENABLE_PERSISTENT_NOTIFICATIONS,
    CONF_HEALTH_RECONCILE_HOUR,
    CONF_HEALTH_RECONCILE_MINUTE,
    CONF_IMPORT_RACHIO_ZONE_PHOTOS,
    CONF_MOISTURE_SENSOR_ENTITIES,
    CONF_OBSERVE_FIRST,
    CONF_RACHIO_CONFIG_ENTRY_ID,
    CONF_RAIN_ACTUALS_ENTITY,
    CONF_RAIN_SOURCE_MODE,
    CONF_SAFE_WINDOW_END_HOUR,
    CONF_SCHEDULE_MOISTURE_MAP,
    CONF_SITE_NAME,
    CONF_WEATHER_UNDERGROUND_API_KEY,
    CONF_WEATHER_UNDERGROUND_STATION_ID,
    CONF_ZONE_COUNT,
    DEFAULT_ALLOW_MOISTURE_WRITE_BACK,
    DEFAULT_AUTO_CATCH_UP_SCHEDULES,
    DEFAULT_AUTO_MOISTURE_WRITE_SCHEDULES,
    DEFAULT_AUTO_MISSED_RUN_SCHEDULES,
    DEFAULT_ENABLE_PERSISTENT_NOTIFICATIONS,
    DEFAULT_HEALTH_RECONCILE_HOUR,
    DEFAULT_HEALTH_RECONCILE_MINUTE,
    DEFAULT_IMPORT_RACHIO_ZONE_PHOTOS,
    DEFAULT_MOISTURE_SENSOR_ENTITIES,
    DEFAULT_RAIN_SOURCE_MODE,
    DEFAULT_SCHEDULE_MOISTURE_MAP,
    DEFAULT_OBSERVE_FIRST,
    DEFAULT_SAFE_WINDOW_END_HOUR,
    DEFAULT_ZONE_COUNT,
    DOMAIN,
    RAIN_SOURCE_MODE_ENTITY,
    RAIN_SOURCE_MODE_NONE,
    RAIN_SOURCE_MODE_WEATHER_UNDERGROUND,
)
from .discovery import (
    discover_linked_entities,
    rachio_entry_options,
    schedule_entity_options,
)

_LOGGER = logging.getLogger(__name__)

MOISTURE_SENSOR_FIELD = "moisture_sensor_entity"
MOISTURE_SCHEDULE_CONTEXT_FIELD = "schedule_name"
UNMAPPED_SENTINEL = "__unmapped__"
MOISTURE_SENSOR_HINTS = ("soil_moisture", "soil moisture", "moisture")
MOISTURE_SENSOR_EXCLUDE_HINTS = (
    "battery",
    "calibration",
    "humidity",
    "linkquality",
    "sampling",
    "temperature",
    "warning",
)
RAIN_SOURCE_OPTIONS = [
    selector.SelectOptionDict(
        value=RAIN_SOURCE_MODE_ENTITY,
        label="Home Assistant observed-rain entity",
    ),
    selector.SelectOptionDict(
        value=RAIN_SOURCE_MODE_WEATHER_UNDERGROUND,
        label="Weather Underground PWS station",
    ),
    selector.SelectOptionDict(
        value=RAIN_SOURCE_MODE_NONE,
        label="Not configured yet",
    ),
]
WEATHER_UNDERGROUND_STATION_RE = r"^[A-Z0-9_-]{3,32}$"


def _moisture_field_key(_schedule_label: str) -> str:
    """Return the stable form-field key for one schedule mapping step."""
    return MOISTURE_SENSOR_FIELD


def _submitted_field_value(
    user_input: dict[str, Any],
    field_key: str = MOISTURE_SENSOR_FIELD,
    option_tokens: dict[str, str] | None = None,
    default: str = UNMAPPED_SENTINEL,
) -> str:
    """Return the submitted moisture sensor value.

    The normal path uses ``moisture_sensor_entity`` as a stable ASCII key. The
    fallback scan is intentionally retained for older clients and HA surfaces
    that post the visible option label instead of the canonical entity id.
    """
    option_tokens = option_tokens or {}
    candidates: list[str] = []
    if field_key in user_input:
        candidates.append(str(user_input[field_key]))
    candidates.extend(
        str(value)
        for key, value in user_input.items()
        if key not in {field_key, MOISTURE_SCHEDULE_CONTEXT_FIELD}
    )
    for candidate in candidates:
        if candidate in option_tokens:
            return option_tokens[candidate]
    for candidate in candidates:
        if candidate:
            return candidate
    return default


def _selected_values_in_options(
    values: Any,
    options: list[tuple[str, str]],
) -> list[str]:
    """Return saved selector values that still exist in the current options."""
    valid_values = {value for value, _label in options}
    if not isinstance(values, list):
        values = list(values or [])
    return [value for value in values if isinstance(value, str) and value in valid_values]


def _normalise_basic_input(
    user_input: dict[str, Any],
    defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return normalized setup/options input without dropping saved secrets."""
    defaults = defaults or {}
    normalised = dict(user_input)
    mode = str(
        normalised.get(
            CONF_RAIN_SOURCE_MODE,
            defaults.get(CONF_RAIN_SOURCE_MODE, DEFAULT_RAIN_SOURCE_MODE),
        )
        or DEFAULT_RAIN_SOURCE_MODE
    )
    normalised[CONF_RAIN_SOURCE_MODE] = mode
    station_id = str(
        normalised.get(
            CONF_WEATHER_UNDERGROUND_STATION_ID,
            defaults.get(CONF_WEATHER_UNDERGROUND_STATION_ID, ""),
        )
        or ""
    ).strip().upper()
    normalised[CONF_WEATHER_UNDERGROUND_STATION_ID] = station_id
    api_key = str(normalised.get(CONF_WEATHER_UNDERGROUND_API_KEY, "") or "").strip()
    if not api_key:
        api_key = str(defaults.get(CONF_WEATHER_UNDERGROUND_API_KEY, "") or "").strip()
    normalised[CONF_WEATHER_UNDERGROUND_API_KEY] = api_key
    return normalised


def _basic_input_errors(user_input: dict[str, Any]) -> dict[str, str]:
    """Return config-flow errors for the selected rain-source mode."""
    errors: dict[str, str] = {}
    if user_input.get(CONF_RAIN_SOURCE_MODE) != RAIN_SOURCE_MODE_WEATHER_UNDERGROUND:
        return errors
    station_id = str(user_input.get(CONF_WEATHER_UNDERGROUND_STATION_ID, "") or "")
    api_key = str(user_input.get(CONF_WEATHER_UNDERGROUND_API_KEY, "") or "")
    if not station_id:
        errors[CONF_WEATHER_UNDERGROUND_STATION_ID] = "required"
    elif re.fullmatch(WEATHER_UNDERGROUND_STATION_RE, station_id) is None:
        errors[CONF_WEATHER_UNDERGROUND_STATION_ID] = "invalid_station_id"
    if not api_key:
        errors[CONF_WEATHER_UNDERGROUND_API_KEY] = "required"
    return errors


def discover_moisture_sensor_entities(hass) -> list[str]:
    """Return likely soil-moisture sensor entities for config defaults."""
    states_obj = getattr(hass, "states", None)
    async_all = getattr(states_obj, "async_all", None)
    if not callable(async_all):
        return []
    try:
        states = list(async_all("sensor"))
    except TypeError:
        states = [
            state
            for state in async_all()
            if str(getattr(state, "entity_id", "")).startswith("sensor.")
        ]

    candidates: list[tuple[int, str]] = []
    for state in states:
        entity_id = str(getattr(state, "entity_id", ""))
        attributes = getattr(state, "attributes", {}) or {}
        label = " ".join(
            [
                entity_id,
                str(attributes.get("friendly_name", "")),
                str(attributes.get("device_class", "")),
                str(attributes.get("unit_of_measurement", "")),
            ]
        ).lower()
        if any(excluded in label for excluded in MOISTURE_SENSOR_EXCLUDE_HINTS):
            continue
        if not any(hint in label for hint in MOISTURE_SENSOR_HINTS):
            continue
        score = 1
        if "soil" in label:
            score += 1
        if "moisture" in label:
            score += 1
        if attributes.get("unit_of_measurement") == "%":
            score += 1
        candidates.append((score, entity_id))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [entity_id for _score, entity_id in candidates]


def discover_zone_count(hass, rachio_config_entry_id: str | None) -> int | None:
    """Return discovered linked Rachio zone count for form defaults."""
    if not rachio_config_entry_id:
        return None
    try:
        linked_entities = discover_linked_entities(hass, rachio_config_entry_id)
    except (AttributeError, TypeError, ValueError):
        return None
    count = len(linked_entities.zone_entities) or len(linked_entities.zone_switches)
    return count or None


def _log_moisture_mapping_submission(
    schedule_entity_id: str,
    schedule_label: str,
    user_input: dict[str, Any],
    selected: str,
) -> None:
    """Log enough options-flow evidence to debug HA form handoff issues."""
    _LOGGER.debug(
        "Moisture mapping submit: schedule_entity_id=%s schedule_label=%s "
        "user_input_keys=%s resolved_selected=%s",
        schedule_entity_id,
        schedule_label,
        sorted(str(key) for key in user_input),
        selected,
    )


def _flow_schema(
    rachio_options: list[tuple[str, str]],
    defaults: dict[str, Any] | None = None,
    moisture_sensor_defaults: list[str] | None = None,
    zone_count_default: int | None = None,
) -> vol.Schema:
    """Build the shared config form schema.

    Rain actuals and moisture candidates stay optional so the integration can be
    installed in observe-first shadow mode before those evidence sources are
    finalized.
    """
    defaults = defaults or {}
    available_rachio_entry_ids = {value for value, _label in rachio_options}
    selected_rachio_entry_id = defaults.get(CONF_RACHIO_CONFIG_ENTRY_ID)
    if selected_rachio_entry_id not in available_rachio_entry_ids and rachio_options:
        selected_rachio_entry_id = rachio_options[0][0]

    moisture_defaults = defaults.get(CONF_MOISTURE_SENSOR_ENTITIES)
    if moisture_defaults is None:
        moisture_defaults = (
            moisture_sensor_defaults
            if moisture_sensor_defaults is not None
            else DEFAULT_MOISTURE_SENSOR_ENTITIES
        )
    if not isinstance(moisture_defaults, list):
        moisture_defaults = list(moisture_defaults or [])

    schema: dict[Any, Any] = {
        vol.Required(
            CONF_SITE_NAME,
            default=defaults.get(CONF_SITE_NAME, "Rachio Site"),
        ): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Required(
            CONF_RACHIO_CONFIG_ENTRY_ID,
            default=selected_rachio_entry_id or "",
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
            CONF_RAIN_SOURCE_MODE,
            default=defaults.get(CONF_RAIN_SOURCE_MODE, DEFAULT_RAIN_SOURCE_MODE),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=RAIN_SOURCE_OPTIONS,
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Required(
            CONF_ZONE_COUNT,
            default=defaults.get(
                CONF_ZONE_COUNT,
                zone_count_default or DEFAULT_ZONE_COUNT,
            ),
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
            CONF_ENABLE_PERSISTENT_NOTIFICATIONS,
            default=defaults.get(
                CONF_ENABLE_PERSISTENT_NOTIFICATIONS,
                DEFAULT_ENABLE_PERSISTENT_NOTIFICATIONS,
            ),
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_IMPORT_RACHIO_ZONE_PHOTOS,
            default=defaults.get(
                CONF_IMPORT_RACHIO_ZONE_PHOTOS,
                DEFAULT_IMPORT_RACHIO_ZONE_PHOTOS,
            ),
        ): selector.BooleanSelector(),
        vol.Required(
            CONF_SAFE_WINDOW_END_HOUR,
            default=defaults.get(
                CONF_SAFE_WINDOW_END_HOUR,
                DEFAULT_SAFE_WINDOW_END_HOUR,
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_HEALTH_RECONCILE_HOUR,
            default=defaults.get(
                CONF_HEALTH_RECONCILE_HOUR,
                DEFAULT_HEALTH_RECONCILE_HOUR,
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=23, step=1, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Required(
            CONF_HEALTH_RECONCILE_MINUTE,
            default=defaults.get(
                CONF_HEALTH_RECONCILE_MINUTE,
                DEFAULT_HEALTH_RECONCILE_MINUTE,
            ),
        ): selector.NumberSelector(
            selector.NumberSelectorConfig(min=0, max=59, step=1, mode=selector.NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_MOISTURE_SENSOR_ENTITIES,
            default=moisture_defaults,
        ): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", multiple=True)
        ),
    }

    # Do not force an empty-string entity id into the selector. Older flow
    # iterations did that and produced an invalid optional default.
    rain_default = defaults.get(CONF_RAIN_ACTUALS_ENTITY)
    rain_marker: Any = vol.Optional(CONF_RAIN_ACTUALS_ENTITY)
    if rain_default not in (None, ""):
        rain_marker = vol.Optional(
            CONF_RAIN_ACTUALS_ENTITY,
            default=rain_default,
        )
    schema[rain_marker] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["sensor", "weather"], multiple=False)
    )
    schema[
        vol.Optional(
            CONF_WEATHER_UNDERGROUND_STATION_ID,
            default=defaults.get(CONF_WEATHER_UNDERGROUND_STATION_ID, ""),
        )
    ] = selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
    )
    schema[vol.Optional(CONF_WEATHER_UNDERGROUND_API_KEY)] = selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
    )

    return vol.Schema(schema)


def _policy_schema(
    schedule_options: list[tuple[str, str]],
    defaults: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the schedule policy schema."""
    defaults = defaults or {}
    default_auto_catch_up = _selected_values_in_options(
        defaults.get(
            CONF_AUTO_CATCH_UP_SCHEDULES,
            DEFAULT_AUTO_CATCH_UP_SCHEDULES,
        ),
        schedule_options,
    )
    default_auto_missed = _selected_values_in_options(
        defaults.get(
            CONF_AUTO_MISSED_RUN_SCHEDULES,
            DEFAULT_AUTO_MISSED_RUN_SCHEDULES,
        ),
        schedule_options,
    )
    default_auto_moisture = _selected_values_in_options(
        defaults.get(
            CONF_AUTO_MOISTURE_WRITE_SCHEDULES,
            DEFAULT_AUTO_MOISTURE_WRITE_SCHEDULES,
        ),
        schedule_options,
    )
    return vol.Schema(
        {
            vol.Required(
                CONF_AUTO_CATCH_UP_SCHEDULES,
                default=default_auto_catch_up,
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
            vol.Required(
                CONF_AUTO_MISSED_RUN_SCHEDULES,
                default=default_auto_missed,
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
            vol.Required(
                CONF_AUTO_MOISTURE_WRITE_SCHEDULES,
                default=default_auto_moisture,
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
            normalised = _normalise_basic_input(user_input)
            errors = _basic_input_errors(normalised)
            if errors:
                return self.async_show_form(
                    step_id="user",
                    data_schema=_flow_schema(
                        options,
                        normalised,
                        moisture_sensor_defaults=discover_moisture_sensor_entities(
                            self.hass
                        ),
                        zone_count_default=discover_zone_count(
                            self.hass,
                            options[0][0] if options else None,
                        ),
                    ),
                    errors=errors,
                )
            self._basic_input = normalised
            return await self.async_step_policy()

        return self.async_show_form(
            step_id="user",
            data_schema=_flow_schema(
                options,
                moisture_sensor_defaults=discover_moisture_sensor_entities(self.hass),
                zone_count_default=discover_zone_count(
                    self.hass,
                    options[0][0] if options else None,
                ),
            ),
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
                ),
                CONF_AUTO_MISSED_RUN_SCHEDULES: user_input.get(
                    CONF_AUTO_MISSED_RUN_SCHEDULES,
                    [],
                ),
                CONF_AUTO_MOISTURE_WRITE_SCHEDULES: user_input.get(
                    CONF_AUTO_MOISTURE_WRITE_SCHEDULES,
                    [],
                ),
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
        if not moisture_candidates:
            # Skip the mapping step entirely when the operator has not selected
            # moisture sensors. An empty mapping is an intentional valid state.
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
        field_key = _moisture_field_key(schedule_label)
        option_tokens = {UNMAPPED_SENTINEL: UNMAPPED_SENTINEL, "Unmapped": UNMAPPED_SENTINEL}
        for entity_id in moisture_candidates:
            state = self.hass.states.get(entity_id)
            label = str(state.attributes.get("friendly_name")) if state else entity_id
            option_tokens[entity_id] = entity_id
            option_tokens[label] = entity_id
        if user_input is not None:
            selected = _submitted_field_value(user_input, field_key, option_tokens)
            _log_moisture_mapping_submission(
                schedule_entity_id,
                schedule_label,
                user_input,
                selected,
            )
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
                vol.Optional(
                    MOISTURE_SCHEDULE_CONTEXT_FIELD,
                    default=schedule_label,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
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
        self._entry = config_entry
        self._basic_input: dict[str, Any] = {}
        self._policy_input: dict[str, Any] = {}
        self._schedule_options: list[tuple[str, str]] = []
        self._moisture_mapping: dict[str, str] = {}
        self._mapping_index = 0

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the integration options."""
        defaults = {**self._entry.data, **self._entry.options}
        options = rachio_entry_options(self.hass)
        if not options:
            return self.async_abort(reason="no_rachio_entries")

        if user_input is not None:
            normalised = _normalise_basic_input(user_input, defaults)
            errors = _basic_input_errors(normalised)
            if errors:
                return self.async_show_form(
                    step_id="init",
                    data_schema=_flow_schema(
                        options,
                        normalised,
                        moisture_sensor_defaults=discover_moisture_sensor_entities(
                            self.hass
                        ),
                        zone_count_default=discover_zone_count(
                            self.hass,
                            normalised.get(CONF_RACHIO_CONFIG_ENTRY_ID),
                        ),
                    ),
                    errors=errors,
                )
            self._basic_input = normalised
            return await self.async_step_policy()

        return self.async_show_form(
            step_id="init",
            data_schema=_flow_schema(
                options,
                defaults,
                moisture_sensor_defaults=discover_moisture_sensor_entities(self.hass),
                zone_count_default=discover_zone_count(
                    self.hass,
                    defaults.get(CONF_RACHIO_CONFIG_ENTRY_ID),
                ),
            ),
        )

    async def async_step_policy(self, user_input: dict[str, Any] | None = None):
        """Manage schedule policy options."""
        defaults = {**self._entry.data, **self._entry.options}
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
                ),
                CONF_AUTO_MISSED_RUN_SCHEDULES: user_input.get(
                    CONF_AUTO_MISSED_RUN_SCHEDULES,
                    [],
                ),
                CONF_AUTO_MOISTURE_WRITE_SCHEDULES: user_input.get(
                    CONF_AUTO_MOISTURE_WRITE_SCHEDULES,
                    [],
                ),
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
        defaults = {**self._entry.data, **self._entry.options}
        moisture_candidates = [
            entity_id
            for entity_id in self._basic_input.get(
                CONF_MOISTURE_SENSOR_ENTITIES,
                defaults.get(CONF_MOISTURE_SENSOR_ENTITIES, []),
            )
            if isinstance(entity_id, str)
        ]
        existing_map = defaults.get(CONF_SCHEDULE_MOISTURE_MAP, DEFAULT_SCHEDULE_MOISTURE_MAP)

        if not moisture_candidates:
            return self.async_create_entry(
                title="",
                data={
                    **self._basic_input,
                    **self._policy_input,
                    CONF_SCHEDULE_MOISTURE_MAP: DEFAULT_SCHEDULE_MOISTURE_MAP,
                },
            )

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
        field_key = _moisture_field_key(schedule_label)
        option_tokens = {UNMAPPED_SENTINEL: UNMAPPED_SENTINEL, "Unmapped": UNMAPPED_SENTINEL}
        for entity_id in moisture_candidates:
            state = self.hass.states.get(entity_id)
            label = str(state.attributes.get("friendly_name")) if state else entity_id
            option_tokens[entity_id] = entity_id
            option_tokens[label] = entity_id
        if user_input is not None:
            selected = _submitted_field_value(user_input, field_key, option_tokens)
            _log_moisture_mapping_submission(
                schedule_entity_id,
                schedule_label,
                user_input,
                selected,
            )
            if selected != UNMAPPED_SENTINEL:
                self._moisture_mapping[schedule_entity_id] = selected
            self._mapping_index += 1
            return await self.async_step_moisture_map()

        options = [selector.SelectOptionDict(value=UNMAPPED_SENTINEL, label="Unmapped")]
        available_moisture_entities = set()
        for entity_id in moisture_candidates:
            available_moisture_entities.add(entity_id)
            state = self.hass.states.get(entity_id)
            label = str(state.attributes.get("friendly_name")) if state else entity_id
            options.append(selector.SelectOptionDict(value=entity_id, label=label))
        default_value = existing_map.get(schedule_entity_id, UNMAPPED_SENTINEL)
        if default_value not in available_moisture_entities:
            default_value = UNMAPPED_SENTINEL
        schema = vol.Schema(
            {
                vol.Optional(
                    MOISTURE_SCHEDULE_CONTEXT_FIELD,
                    default=schedule_label,
                ): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                ),
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
