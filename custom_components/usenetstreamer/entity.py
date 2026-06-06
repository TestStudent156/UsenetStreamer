"""Base entity for UsenetStreamer."""
from __future__ import annotations

from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import UsenetStreamerCoordinator


class UsenetStreamerEntity(CoordinatorEntity[UsenetStreamerCoordinator]):
    """Base entity tying entities to one device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: UsenetStreamerCoordinator, entry_id: str
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name="UsenetStreamer",
        )
