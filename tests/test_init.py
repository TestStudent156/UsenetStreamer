"""Tests for UsenetStreamer setup/unload/remove with add-on management."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.hassio import AddonInfo, AddonState
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.usenetstreamer import async_remove_entry
from custom_components.usenetstreamer.const import (
    CONF_INTEGRATION_CREATED_ADDON,
    CONF_USE_ADDON,
    DOMAIN,
)

ADDON = "custom_components.usenetstreamer.addon.get_addon_manager"
GETDATA = "custom_components.usenetstreamer.UsenetStreamerClient.async_get_data"
FAKE = {"addonVersion": "1.7.12", "values": {}}
ENTRY_DATA = {
    "host": "local-usenetstreamer",
    "port": 7000,
    "ssl": False,
    "admin_token": "SECRET",
    "verify_ssl": True,
    CONF_USE_ADDON: True,
    CONF_INTEGRATION_CREATED_ADDON: True,
}


def _info(state: AddonState) -> AddonInfo:
    return AddonInfo(
        available=True,
        hostname="local-usenetstreamer",
        options={"shared_secret": "SECRET"},
        state=state,
        update_available=False,
        version="1.7.12",
    )


def _mgr(state: AddonState) -> MagicMock:
    mgr = MagicMock()
    mgr.async_get_addon_info = AsyncMock(return_value=_info(state))
    mgr.async_schedule_start_addon = MagicMock()
    mgr.async_start_addon = AsyncMock()
    mgr.async_stop_addon = AsyncMock()
    mgr.async_uninstall_addon = AsyncMock()
    return mgr


def _entry(hass: HomeAssistant, **overrides) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data={**ENTRY_DATA, **overrides}
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_retry_when_addon_not_running(hass: HomeAssistant) -> None:
    mgr = _mgr(AddonState.NOT_RUNNING)
    entry = _entry(hass)
    with patch(ADDON, return_value=mgr):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    mgr.async_schedule_start_addon.assert_called_once()


async def test_setup_succeeds_when_addon_running(hass: HomeAssistant) -> None:
    mgr = _mgr(AddonState.RUNNING)
    entry = _entry(hass)
    with patch(ADDON, return_value=mgr), patch(GETDATA, return_value=FAKE):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_remove_uninstalls_owned_addon(hass: HomeAssistant) -> None:
    mgr = _mgr(AddonState.RUNNING)
    entry = _entry(hass)
    with patch(ADDON, return_value=mgr):
        await async_remove_entry(hass, entry)
    mgr.async_uninstall_addon.assert_awaited_once()


async def test_remove_keeps_addon_when_not_owned(hass: HomeAssistant) -> None:
    mgr = _mgr(AddonState.RUNNING)
    entry = _entry(hass, integration_created_addon=False)
    with patch(ADDON, return_value=mgr):
        await async_remove_entry(hass, entry)
    mgr.async_uninstall_addon.assert_not_awaited()


async def test_disable_stops_addon(hass: HomeAssistant) -> None:
    mgr = _mgr(AddonState.RUNNING)
    entry = _entry(hass)
    with patch(ADDON, return_value=mgr), patch(GETDATA, return_value=FAKE):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await hass.config_entries.async_set_disabled_by(
            entry.entry_id, ConfigEntryDisabler.USER
        )
        await hass.async_block_till_done()
    mgr.async_stop_addon.assert_awaited_once()
