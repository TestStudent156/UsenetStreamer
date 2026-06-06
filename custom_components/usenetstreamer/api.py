"""Async client for the UsenetStreamer admin API."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


class UsenetStreamerError(Exception):
    """Base error."""


class CannotConnect(UsenetStreamerError):
    """Cannot reach the server."""


class InvalidAuth(UsenetStreamerError):
    """Admin token rejected."""


class UsenetStreamerClient:
    """Talks to the UsenetStreamer admin API."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        ssl: bool,
        admin_token: str,
        verify_ssl: bool,
    ) -> None:
        self._session = async_get_clientsession(hass, verify_ssl)
        scheme = "https" if ssl else "http"
        self._config_url = f"{scheme}://{host}:{port}/admin/api/config"
        self._headers = {"X-Addon-Token": admin_token}

    async def async_get_data(self) -> dict[str, Any]:
        try:
            async with asyncio.timeout(10):
                resp = await self._session.get(
                    self._config_url, headers=self._headers
                )
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CannotConnect from err
        if resp.status in (401, 403):
            raise InvalidAuth
        if resp.status >= 400:
            raise CannotConnect
        return await resp.json(content_type=None)

    async def async_set_config(self, values: dict[str, Any]) -> dict[str, Any]:
        try:
            async with asyncio.timeout(15):
                resp = await self._session.post(
                    self._config_url,
                    headers=self._headers,
                    json={"values": values},
                )
        except (TimeoutError, aiohttp.ClientError) as err:
            raise CannotConnect from err
        if resp.status in (401, 403):
            raise InvalidAuth
        if resp.status >= 400:
            raise CannotConnect
        return await resp.json(content_type=None)

    async def async_validate(self) -> None:
        await self.async_get_data()
