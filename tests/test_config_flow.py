"""Tests for the UsenetStreamer config flow."""
from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.usenetstreamer.api import CannotConnect, InvalidAuth
from custom_components.usenetstreamer.const import DOMAIN

USER_INPUT = {
    "host": "1.2.3.4", "port": 7000, "ssl": False,
    "admin_token": "TOK", "verify_ssl": True,
}


async def _start(hass):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow_success(hass):
    result = await _start(hass)
    assert result["type"] == FlowResultType.FORM
    with patch(
        "custom_components.usenetstreamer.config_flow."
        "UsenetStreamerClient.async_validate",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == "1.2.3.4"


async def test_user_flow_invalid_auth(hass):
    result = await _start(hass)
    with patch(
        "custom_components.usenetstreamer.config_flow."
        "UsenetStreamerClient.async_validate",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_cannot_connect(hass):
    result = await _start(hass)
    with patch(
        "custom_components.usenetstreamer.config_flow."
        "UsenetStreamerClient.async_validate",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["errors"] == {"base": "cannot_connect"}
