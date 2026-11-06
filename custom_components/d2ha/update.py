"""Update entities: one per container visible in Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import D2HAError
from .const import DOMAIN, JOB_POLL_INTERVAL, JOB_TIMEOUT
from .coordinator import D2HACoordinator
from .entity import D2HAEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: D2HACoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        D2HAContainerUpdate(coordinator, entry.entry_id, container["key"])
        for container in coordinator.data.get("containers", [])
    )


class D2HAContainerUpdate(D2HAEntity, UpdateEntity):
    """The update state of one container; install runs the safe update."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.PROGRESS
        | UpdateEntityFeature.RELEASE_NOTES
    )
    _attr_translation_key = "container_update"

    def __init__(self, coordinator: D2HACoordinator, entry_id: str, key: str) -> None:
        super().__init__(coordinator, entry_id)
        self._key = key
        self._attr_unique_id = f"{entry_id}_{key}_update"
        container = coordinator.container(key) or {}
        self._attr_name = container.get("name", key)

    @property
    def _container(self) -> dict[str, Any]:
        return self.coordinator.container(self._key) or {}

    @property
    def installed_version(self) -> str | None:
        return self._container.get("installed_version")

    @property
    def latest_version(self) -> str | None:
        container = self._container
        if container.get("update") == "available":
            return container.get("latest_version")
        return container.get("installed_version")

    @property
    def release_url(self) -> str | None:
        return self._container.get("release_url") or None

    @property
    def in_progress(self) -> int | bool:
        job = self.coordinator.job_for(self._key, self._container.get("name", ""))
        if not job:
            return False
        percent = job.get("percent")
        return int(percent) if percent is not None else True

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
            "update_status": container.get("update"),
            "breaking_changes": container.get("breaking", False),
            "can_update": container.get("can_update", False),
        }

    async def async_release_notes(self) -> str | None:
        """The release notes of the pending version, as Markdown."""
        if not self._container.get("has_notes"):
            return None
        try:
            notes = await self.coordinator.client.notes(self._key)
        except D2HAError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="notes_failed",
                translation_placeholders={"error": exc.code},
            ) from exc
        if not notes:
            return None
        return notes.get("body")

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Start the update in D2HA and follow the job to the end."""
        container = self._container
        if not container.get("can_update"):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="cannot_update"
            )
        client = self.coordinator.client
        try:
            job_id = await client.update_container(self._key)
        except D2HAError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": exc.code},
            ) from exc
        self.async_write_ha_state()
        await _follow_job(client, job_id, self)
        await self.coordinator.async_request_refresh()


async def _follow_job(client, job_id: str, entity: D2HAContainerUpdate) -> None:
    """Poll the job until it ends; raise with the D2HA error code on failure."""
    elapsed = 0.0
    while elapsed < JOB_TIMEOUT:
        try:
            job = await client.job(job_id)
        except D2HAError:
            job = None
        if job is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="job_lost"
            )
        entity.async_write_ha_state()
        state = job.get("state")
        if state == "done":
            return
        if state == "failed":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": job.get("error", "error.generic")},
            )
        await asyncio.sleep(JOB_POLL_INTERVAL)
        elapsed += JOB_POLL_INTERVAL
    raise HomeAssistantError(translation_domain=DOMAIN, translation_key="job_timeout")
