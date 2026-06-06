"""Tests for the UsenetStreamer API client."""
from __future__ import annotations

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.usenetstreamer.api import (
    CannotConnect,
    InvalidAuth,
    UsenetStreamerClient,
)


@pytest.fixture
async def client(hass):
    return UsenetStreamerClient(
        hass=hass, host="1.2.3.4", port=7000, ssl=False,
        admin_token="TOK", verify_ssl=True,
    )


async def test_get_data_success(client):
    url = "http://1.2.3.4:7000/admin/api/config"
    payload = {
        "addonVersion": "1.2.3",
        "values": {"INDEXER_MANAGER": "prowlarr",
                   "INDEXER_MANAGER_INDEXERS": "-1",
                   "EASYNEWS_ENABLED": "true",
                   "NZB_TRIAGE_ENABLED": "false"},
    }
    with aioresponses() as m:
        m.get(url, payload=payload)
        data = await client.async_get_data()
    assert data["addonVersion"] == "1.2.3"
    assert data["values"]["INDEXER_MANAGER"] == "prowlarr"


async def test_invalid_auth_raises(client):
    with aioresponses() as m:
        m.get("http://1.2.3.4:7000/admin/api/config", status=401)
        with pytest.raises(InvalidAuth):
            await client.async_validate()


async def test_cannot_connect_raises(client):
    with aioresponses() as m:
        m.get("http://1.2.3.4:7000/admin/api/config",
              exception=TimeoutError())
        with pytest.raises(CannotConnect):
            await client.async_validate()
