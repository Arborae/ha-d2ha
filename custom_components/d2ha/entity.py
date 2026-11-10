"""Base entities for the D2HA integration."""

from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import D2HACoordinator


class D2HAEntity(CoordinatorEntity[D2HACoordinator]):
    """Server-level entities hang off one device: the D2HA server."""

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


class D2HAContainerEntity(D2HAEntity):
    """Container-level entities: one device per container, under the server."""

    def __init__(
        self,
        coordinator: D2HACoordinator,
        entry_id: str,
        key: str,
        known: set[str],
    ) -> None:
        super().__init__(coordinator, entry_id)
        self._key = key
        # The keys its platform has entities for.
        self._known = known
        container = coordinator.container(key) or {}
        server = dr.async_get(coordinator.hass).async_get_device_by_identifier(
            (DOMAIN, entry_id), entry_id
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{key}")},
            via_device_id=server.id if server else None,
            name=container.get("name", key),
        )

    async def async_removed_from_registry(self) -> None:
        """Deleted with its device: a container that comes back gets new entities."""
        self._known.discard(self._key)
