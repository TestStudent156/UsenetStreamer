"""Tests for UsenetStreamer services."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.usenetstreamer.const import DOMAIN

ENTRY_DATA = {
    "host": "1.2.3.4",
    "port": 7000,
    "ssl": False,
    "admin_token": "TOK",
    "verify_ssl": True,
}
FAKE = {"addonVersion": "1.2.3", "values": {}}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.usenetstreamer.UsenetStreamerClient.async_get_data",
        return_value=FAKE,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_apply_config_service_calls_client(hass: HomeAssistant) -> None:
    entry = await _setup(hass)
    with (
        patch(
            "custom_components.usenetstreamer.UsenetStreamerClient.async_set_config",
            new=AsyncMock(return_value={"success": True}),
        ) as set_config,
        patch(
            "custom_components.usenetstreamer.UsenetStreamerClient.async_get_data",
            new=AsyncMock(return_value=FAKE),
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            "apply_config",
            {"entry_id": entry.entry_id, "values": {"EASYNEWS_ENABLED": True}},
            blocking=True,
        )

    set_config.assert_awaited_once_with({"EASYNEWS_ENABLED": True})


async def test_apply_config_service_invalid_entry(hass: HomeAssistant) -> None:
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            "apply_config",
            {"entry_id": "missing", "values": {"EASYNEWS_ENABLED": True}},
            blocking=True,
        )
