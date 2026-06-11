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
# The add-on slug that was discovered at config-flow time. Stored on the
# config entry so subsequent setup calls don't have to re-enumerate the
# Supervisor store. Falls back to ADDON_SLUG_LEGACY when absent (e.g. for
# upgrades from the original MVP).
CONF_DISCOVERED_SLUG = "discovered_slug"
ATTR_ENTRY_ID = "entry_id"
ATTR_VALUES = "values"

# The legacy literal slug baked into the parent design spec — kept as a
# fallback for the local-add-on install path and for tests.
ADDON_SLUG_LEGACY = "local_usenetstreamer"
# Suffix matched by slug discovery to find store-installed copies whose
# slug has been hash-prefixed by `store.add_repository`.
ADDON_SLUG_SUFFIX = "_usenetstreamer"
# Back-compat alias for any code that still imports the old name.
ADDON_SLUG = ADDON_SLUG_LEGACY
ADDON_NAME = "UsenetStreamer"

DEFAULT_PORT = 7000
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True
DEFAULT_SCAN_INTERVAL = 60  # seconds

# Retry policy for add-on writes / starts. Conservative defaults — the
# Supervisor is local and either responds fast or hangs.
OPTIONS_WRITE_MAX_RETRIES = 3
OPTIONS_WRITE_BASE_BACKOFF = 0.5  # seconds; doubles on each attempt

MANUFACTURER = "Sanket9225"
MODEL = "UsenetStreamer"
