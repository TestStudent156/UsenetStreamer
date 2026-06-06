"""The UsenetStreamer integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .api import UsenetStreamerClient
from .const import (
    CONF_ADMIN_TOKEN,
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
)
from .coordinator import UsenetStreamerCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type UsenetStreamerConfigEntry = ConfigEntry[UsenetStreamerCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: UsenetStreamerConfigEntry
) -> bool:
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
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
