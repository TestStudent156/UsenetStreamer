"""Supervisor add-on management for UsenetStreamer."""
from __future__ import annotations

import logging

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.singleton import singleton

from .const import ADDON_NAME, ADDON_SLUG, DOMAIN

LOGGER = logging.getLogger(__name__)
DATA_ADDON_MANAGER = f"{DOMAIN}_addon_manager"


@singleton(DATA_ADDON_MANAGER)
@callback
def get_addon_manager(hass: HomeAssistant) -> AddonManager:
    """Return the singleton add-on manager for the UsenetStreamer add-on."""
    return AddonManager(hass, LOGGER, ADDON_NAME, ADDON_SLUG)


async def async_ensure_addon_running(hass: HomeAssistant) -> AddonInfo:
    """Make sure the add-on is installed and running.

    Raises ConfigEntryNotReady (so HA retries setup) while the add-on is
    missing, installing, or still starting.
    """
    addon_manager = get_addon_manager(hass)
    try:
        addon_info = await addon_manager.async_get_addon_info()
    except AddonError as err:
        raise ConfigEntryNotReady(str(err)) from err

    if addon_info.state is AddonState.NOT_INSTALLED:
        raise ConfigEntryNotReady("UsenetStreamer add-on is not installed")
    if addon_info.state in (AddonState.INSTALLING, AddonState.UPDATING):
        raise ConfigEntryNotReady("UsenetStreamer add-on is installing")
    if addon_info.state is AddonState.NOT_RUNNING:
        addon_manager.async_schedule_start_addon()
        raise ConfigEntryNotReady("UsenetStreamer add-on is starting")
    return addon_info
