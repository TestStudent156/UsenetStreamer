"""Constants for the UsenetStreamer integration."""
from __future__ import annotations

DOMAIN = "usenetstreamer"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SSL = "ssl"
CONF_ADMIN_TOKEN = "admin_token"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
ATTR_ENTRY_ID = "entry_id"
ATTR_VALUES = "values"

DEFAULT_PORT = 7000
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_SCAN_INTERVAL = 60  # seconds

MANUFACTURER = "Sanket9225"
MODEL = "UsenetStreamer"
