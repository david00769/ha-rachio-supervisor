"""Constants for Rachio Supervisor."""

from __future__ import annotations

DOMAIN = "rachio_supervisor"
TITLE = "Rachio Supervisor"
VERSION = "0.1.0"
RACHIO_DOMAIN = "rachio"
CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_WEBHOOK_ID = "webhook_id"
WEBHOOK_CONST_ID = "homeassistant.rachio:"

CONF_SITE_NAME = "site_name"
CONF_RACHIO_CONFIG_ENTRY_ID = "rachio_config_entry_id"
CONF_RAIN_ACTUALS_ENTITY = "rain_actuals_entity"
CONF_ZONE_COUNT = "zone_count"
CONF_OBSERVE_FIRST = "observe_first"
CONF_ALLOW_MOISTURE_WRITE_BACK = "allow_moisture_write_back"

DEFAULT_ZONE_COUNT = 7
DEFAULT_OBSERVE_FIRST = True
DEFAULT_ALLOW_MOISTURE_WRITE_BACK = False

SERVICE_EVALUATE_NOW = "evaluate_now"
