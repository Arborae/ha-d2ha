"""Buttons: check now, update all, clean images."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import D2HAError
from .coordinator import D2HACoordinator
from .entity import D2HAEntity
from .errors import d2ha_error

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: D2HACoordinator = entry.runtime_data
    buttons: list[ButtonEntity] = [D2HAButton(coordinator, entry.entry_id, "check_now")]
    if not coordinator.data.get("info", {}).get("read_only"):
        buttons += [
            D2HAButton(coordinator, entry.entry_id, "update_all"),
            D2HAButton(coordinator, entry.entry_id, "clean_images"),
        ]
    async_add_entities(buttons)


class D2HAButton(D2HAEntity, ButtonEntity):
    """One action of the D2HA server."""

    def __init__(self, coordinator: D2HACoordinator, entry_id: str, kind: str) -> None:
        super().__init__(coordinator, entry_id)
        self._kind = kind
        self._attr_translation_key = kind
        self._attr_unique_id = f"{entry_id}_{kind}"

    async def async_press(self) -> None:
        client = self.coordinator.client
        try:
            if self._kind == "check_now":
                await client.check_now()
            elif self._kind == "update_all":
                await client.update_all()
            else:
                await client.prune_images()
        except D2HAError as exc:
            # "Update all" with nothing to update is not an error.
            if exc.code != "nothing_to_update":
                raise d2ha_error("action_failed", exc.code) from exc
        # Jobs run in the background in D2HA; the coordinator speeds up while
        # they are active and entities follow the progress from /jobs.
        await self.coordinator.async_request_refresh()
