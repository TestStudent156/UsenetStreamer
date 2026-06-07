"""Constants for the UsenetStreamer integration."""
from __future__ import annotations

DOMAIN = "usenetstreamer"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_SSL = "ssl"
CONF_ADMIN_TOKEN = "admin_token"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_USE_ADDON = "use_addon"
CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
ATTR_ENTRY_ID = "entry_id"
ATTR_VALUES = "values"

# Supervisor add-on that ships UsenetStreamer. The integration installs and
# manages this add-on; the slug is the local-add-on form (folder under /addons).
ADDON_SLUG = "local_usenetstreamer"
ADDON_NAME = "UsenetStreamer"

DEFAULT_PORT = 7000
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_SCAN_INTERVAL = 60  # seconds

MANUFACTURER = "Sanket9225"
MODEL = "UsenetStreamer"
