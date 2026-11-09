"""Sensors: counters for the server, a state sensor per container."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import D2HACoordinator
from .entity import D2HAContainerEntity, D2HAEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: D2HACoordinator = entry.runtime_data
    async_add_entities(
        [
            D2HACounterSensor(coordinator, entry.entry_id, "updates_available"),
            D2HACounterSensor(coordinator, entry.entry_id, "containers_running"),
            D2HACounterSensor(coordinator, entry.entry_id, "unused_images"),
        ]
    )
    known: set[str] = set()

    @callback
    def add_new_containers() -> None:
        """State sensors for containers that appear after the setup."""
        new = [
            container
            for container in coordinator.data.get("containers", [])
            if container["key"] not in known
        ]
        if not new:
            return
        known.update(container["key"] for container in new)
        async_add_entities(
            D2HAContainerStateSensor(coordinator, entry.entry_id, container["key"])
            for container in new
        )

    add_new_containers()
    entry.async_on_unload(coordinator.async_add_listener(add_new_containers))


class D2HACounterSensor(D2HAEntity, SensorEntity):
    """A counter from GET /info (updates, running containers, unused images)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: D2HACoordinator, entry_id: str, kind: str) -> None:
        super().__init__(coordinator, entry_id)
        self._kind = kind
        self._attr_translation_key = kind
        self._attr_unique_id = f"{entry_id}_{kind}"
        if kind == "unused_images":
            # Housekeeping, not a number to watch: it sits under "Diagnostic".
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

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


class D2HAContainerStateSensor(D2HAContainerEntity, SensorEntity):
    """The Docker state of one container (running, exited, ...)."""

    _attr_translation_key = "container_state"

    def __init__(self, coordinator: D2HACoordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator, entry_id, key)
        self._attr_unique_id = f"{entry_id}_{key}_state"

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
