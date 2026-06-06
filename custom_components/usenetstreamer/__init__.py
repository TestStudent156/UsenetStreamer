"""The UsenetStreamer integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ENTRY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .api import UsenetStreamerClient
from .const import (
    ATTR_VALUES,
    CONF_ADMIN_TOKEN,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import UsenetStreamerCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
SERVICE_APPLY_CONFIG = "apply_config"
SERVICE_SCHEMA_APPLY_CONFIG = vol.Schema(
    {
        vol.Required(CONF_ENTRY_ID): cv.string,
        vol.Required(ATTR_VALUES): dict,
    }
)

type UsenetStreamerConfigEntry = ConfigEntry[UsenetStreamerCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: UsenetStreamerConfigEntry
) -> bool:
    if not hass.services.has_service(DOMAIN, SERVICE_APPLY_CONFIG):
        hass.services.async_register(
            DOMAIN,
            SERVICE_APPLY_CONFIG,
            lambda call: _async_handle_apply_config(hass, call.data),
            schema=SERVICE_SCHEMA_APPLY_CONFIG,
        )

    client = UsenetStreamerClient(
        hass=hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        ssl=entry.data[CONF_SSL],
        admin_token=entry.data[CONF_ADMIN_TOKEN],
        verify_ssl=entry.data[CONF_VERIFY_SSL],
    )
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = UsenetStreamerCoordinator(hass, client, scan_interval)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(
    hass: HomeAssistant, entry: UsenetStreamerConfigEntry
) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: UsenetStreamerConfigEntry
) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and not hass.config_entries.async_entries(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_APPLY_CONFIG)
    return unload_ok


async def _async_handle_apply_config(
    hass: HomeAssistant, data: dict[str, Any]
) -> None:
    entry_id = data[CONF_ENTRY_ID]
    values = data[ATTR_VALUES]

    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise HomeAssistantError("Invalid UsenetStreamer config entry")

    coordinator = entry.runtime_data
    await coordinator.async_set_config(values)
    await coordinator.async_request_refresh()
