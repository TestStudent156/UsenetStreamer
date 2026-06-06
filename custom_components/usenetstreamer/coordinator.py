"""DataUpdateCoordinator for UsenetStreamer."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import UsenetStreamerClient, UsenetStreamerError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class UsenetStreamerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the UsenetStreamer admin API on an interval."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: UsenetStreamerClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self._client.async_get_data()
        except UsenetStreamerError as err:
            raise UpdateFailed(str(err)) from err

    async def async_set_config(self, values: dict[str, Any]) -> dict[str, Any]:
        """Apply config values through the admin API."""
        return await self._client.async_set_config(values)
