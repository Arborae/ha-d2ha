"""Sensors: counters for the server, a state sensor per container."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import D2HACoordinator
from .entity import D2HAEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: D2HACoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        D2HACounterSensor(coordinator, entry.entry_id, "updates_available"),
        D2HACounterSensor(coordinator, entry.entry_id, "containers_running"),
        D2HACounterSensor(coordinator, entry.entry_id, "unused_images"),
    ]
    entities += [
        D2HAContainerStateSensor(coordinator, entry.entry_id, container["key"])
        for container in coordinator.data.get("containers", [])
    ]
    async_add_entities(entities)


class D2HACounterSensor(D2HAEntity, SensorEntity):
    """A counter from GET /info (updates, running containers, unused images)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: D2HACoordinator, entry_id: str, kind: str) -> None:
        super().__init__(coordinator, entry_id)
        self._kind = kind
        self._attr_translation_key = kind
        self._attr_unique_id = f"{entry_id}_{kind}"

    @property
    def native_value(self) -> int | None:
        counts = self.coordinator.data.get("info", {}).get("counts", {})
        if self._kind == "updates_available":
            return counts.get("updates")
        if self._kind == "containers_running":
            return counts.get("running")
        return counts.get("unused_images")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._kind == "containers_running":
            counts = self.coordinator.data.get("info", {}).get("counts", {})
            return {"containers": counts.get("containers")}
        if self._kind == "updates_available":
            names = [
                c["name"]
                for c in self.coordinator.data.get("containers", [])
                if c.get("update") == "available"
            ]
            return {"containers": names}
        return None


class D2HAContainerStateSensor(D2HAEntity, SensorEntity):
    """The Docker state of one container (running, exited, ...)."""

    _attr_translation_key = "container_state"

    def __init__(self, coordinator: D2HACoordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator, entry_id)
        self._key = key
        self._attr_unique_id = f"{entry_id}_{key}_state"
        container = coordinator.container(key) or {}
        name = container.get("name", key)
        self._attr_name = f"{name} state"
        self._attr_suggested_object_id = f"d2ha_{name}_state"

    @property
    def _container(self) -> dict[str, Any]:
        return self.coordinator.container(self._key) or {}

    @property
    def native_value(self) -> str | None:
        return self._container.get("state")

    @property
    def available(self) -> bool:
        return super().available and bool(self._container)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        container = self._container
        return {
            "key": self._key,
            "image": container.get("image"),
            "stack": container.get("stack"),
            "status": container.get("status"),
            "health": container.get("health") or None,
            "update_status": container.get("update"),
        }
