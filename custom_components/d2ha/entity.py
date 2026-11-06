"""Base entity for the D2HA integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import D2HACoordinator


class D2HAEntity(CoordinatorEntity[D2HACoordinator]):
    """Everything hangs off one device: the D2HA server."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: D2HACoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        info = coordinator.data.get("info", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="D2HA",
            manufacturer="Arborae",
            sw_version=info.get("version"),
            configuration_url=coordinator.client.url,
        )
