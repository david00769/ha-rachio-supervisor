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
CONF_AUTO_CATCH_UP_SCHEDULES = "auto_catch_up_schedule_entities"
CONF_MOISTURE_SENSOR_ENTITIES = "moisture_sensor_entities"
CONF_SCHEDULE_MOISTURE_MAP = "schedule_moisture_map"
CONF_AUTO_MOISTURE_WRITE_SCHEDULES = "auto_moisture_write_schedule_entities"
CONF_ZONE_COUNT = "zone_count"
CONF_OBSERVE_FIRST = "observe_first"
CONF_ALLOW_MOISTURE_WRITE_BACK = "allow_moisture_write_back"
CONF_AUTO_MISSED_RUN_SCHEDULES = "auto_missed_run_schedule_entities"
CONF_ENABLE_PERSISTENT_NOTIFICATIONS = "enable_persistent_notifications"
CONF_SAFE_WINDOW_END_HOUR = "safe_window_end_hour"
CONF_HEALTH_RECONCILE_HOUR = "health_reconcile_hour"
CONF_HEALTH_RECONCILE_MINUTE = "health_reconcile_minute"
CONF_IMPORT_RACHIO_ZONE_PHOTOS = "import_rachio_zone_photos"

DEFAULT_ZONE_COUNT = 7
DEFAULT_OBSERVE_FIRST = True
DEFAULT_ALLOW_MOISTURE_WRITE_BACK = False
DEFAULT_AUTO_CATCH_UP_SCHEDULES: list[str] = []
DEFAULT_AUTO_MISSED_RUN_SCHEDULES: list[str] = []
DEFAULT_AUTO_MOISTURE_WRITE_SCHEDULES: list[str] = []
DEFAULT_MOISTURE_SENSOR_ENTITIES: list[str] = []
DEFAULT_SCHEDULE_MOISTURE_MAP: dict[str, str] = {}
DEFAULT_ENABLE_PERSISTENT_NOTIFICATIONS = True
DEFAULT_SAFE_WINDOW_END_HOUR = 8
DEFAULT_HEALTH_RECONCILE_HOUR = 12
DEFAULT_HEALTH_RECONCILE_MINUTE = 15
DEFAULT_IMPORT_RACHIO_ZONE_PHOTOS = False

SERVICE_EVALUATE_NOW = "evaluate_now"
SERVICE_RUN_CATCH_UP_NOW = "run_catch_up_now"
SERVICE_QUICK_RUN_ZONE = "quick_run_zone"
SERVICE_WRITE_MOISTURE_NOW = "write_moisture_now"
SERVICE_WRITE_RECOMMENDED_MOISTURE_NOW = "write_recommended_moisture_now"
SERVICE_ACKNOWLEDGE_RECOMMENDATION = "acknowledge_recommendation"
SERVICE_ACKNOWLEDGE_ALL_RECOMMENDATIONS = "acknowledge_all_recommendations"
SERVICE_CLEAR_RECOMMENDATION_ACKNOWLEDGEMENT = "clear_recommendation_acknowledgement"
SERVICE_CLEAR_FLOW_ALERT_REVIEW = "clear_flow_alert_review"
