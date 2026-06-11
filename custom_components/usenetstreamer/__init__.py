"""The UsenetStreamer integration."""
from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.hassio import AddonError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from . import addon
from .api import UsenetStreamerClient
from .const import (
    ATTR_ENTRY_ID,
    ATTR_VALUES,
    CONF_ADMIN_TOKEN,
    CONF_DISCOVERED_SLUG,
    CONF_HOST,
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USE_ADDON,
    CONF_VERIFY_SSL,
    ADDON_SLUG_LEGACY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import UsenetStreamerCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]
SERVICE_APPLY_CONFIG = "apply_config"
SERVICE_SCHEMA_APPLY_CONFIG = vol.Schema(
    {
        vol.Required(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_VALUES): dict,
    }
)

type UsenetStreamerConfigEntry = ConfigEntry[UsenetStreamerCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: UsenetStreamerConfigEntry
) -> bool:
    if entry.data.get(CONF_USE_ADDON):
        slug = entry.data.get(CONF_DISCOVERED_SLUG) or ADDON_SLUG_LEGACY
        await addon.async_ensure_addon_running(hass, slug)

    if not hass.services.has_service(DOMAIN, SERVICE_APPLY_CONFIG):
        hass.services.async_register(
            DOMAIN,
            SERVICE_APPLY_CONFIG,
            partial(_async_handle_apply_config, hass),
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
    if unload_ok and entry.data.get(CONF_USE_ADDON) and entry.disabled_by:
        slug = entry.data.get(CONF_DISCOVERED_SLUG) or ADDON_SLUG_LEGACY
        try:
            await addon.get_addon_manager(hass, slug).async_stop_addon()
        except AddonError as err:
            _LOGGER.error("Failed to stop UsenetStreamer add-on: %s", err)
            return False
    return unload_ok


async def async_remove_entry(
    hass: HomeAssistant, entry: UsenetStreamerConfigEntry
) -> None:
    """Uninstall the add-on if this integration installed it."""
    if not entry.data.get(CONF_INTEGRATION_CREATED_ADDON):
        return
    slug = entry.data.get(CONF_DISCOVERED_SLUG) or ADDON_SLUG_LEGACY
    try:
        await addon.get_addon_manager(hass, slug).async_uninstall_addon()
    except AddonError as err:
        _LOGGER.error("Failed to uninstall UsenetStreamer add-on: %s", err)


async def _async_handle_apply_config(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    data: dict[str, Any] = call.data
    entry_id = data[ATTR_ENTRY_ID]
    values = data[ATTR_VALUES]

    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise HomeAssistantError("Invalid UsenetStreamer config entry")

    coordinator = entry.runtime_data
    await coordinator.async_set_config(values)
    await coordinator.async_request_refresh()
