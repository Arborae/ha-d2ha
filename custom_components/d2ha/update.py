"""Update entities: one per container visible in Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import D2HAError
from .const import DOMAIN, JOB_POLL_INTERVAL, JOB_TIMEOUT
from .coordinator import D2HACoordinator
from .entity import D2HAContainerEntity
from .errors import d2ha_error

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def _image_name(image: str | None) -> str | None:
    """The image reference without tag or digest (a registry port is kept)."""
    if not image:
        return None
    name = image.split("@", 1)[0]
    if name.rfind(":") > name.rfind("/"):
        name = name[: name.rfind(":")]
    return name


async def async_setup_entry(
    hass: HomeAssistant, entry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: D2HACoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new_containers() -> None:
        """Entities for containers that appear after the setup (new, or enabled in D2HA)."""
        new = [
            container
            for container in coordinator.data.get("containers", [])
            if container["key"] not in known
        ]
        if not new:
            return
        known.update(container["key"] for container in new)
        async_add_entities(
            D2HAContainerUpdate(coordinator, entry.entry_id, container["key"], known)
            for container in new
        )

    add_new_containers()
    entry.async_on_unload(coordinator.async_add_listener(add_new_containers))


class D2HAContainerUpdate(D2HAContainerEntity, UpdateEntity):
    """The update state of one container; install runs the safe update."""

    _attr_translation_key = "container_update"
    # The main entity of the container device: no Configuration/Diagnostic category.
    _attr_entity_category = None

    def __init__(
        self,
        coordinator: D2HACoordinator,
        entry_id: str,
        key: str,
        known: set[str],
    ) -> None:
        super().__init__(coordinator, entry_id, key, known)
        self._attr_unique_id = f"{entry_id}_{key}_update"
        self._active_job: dict[str, Any] | None = None

    @property
    def _container(self) -> dict[str, Any]:
        return self.coordinator.container(self._key) or {}

    @property
    def _job(self) -> dict[str, Any] | None:
        """The job updating this container: the one followed live, else the coordinator's."""
        if self._active_job is not None:
            return self._active_job
        return self.coordinator.job_for(self._key, self._container.get("name", ""))

    @property
    def supported_features(self) -> UpdateEntityFeature:
        """Install only when D2HA allows it (API.md: offer install when can_update)."""
        features = UpdateEntityFeature.PROGRESS | UpdateEntityFeature.RELEASE_NOTES
        if self._container.get("can_update"):
            features |= UpdateEntityFeature.INSTALL
        return features

    @property
    def title(self) -> str | None:
        """What is being updated: the image without tag or digest."""
        return _image_name(self._container.get("image"))

    @property
    def installed_version(self) -> str | None:
        return self._container.get("installed_version")

    @property
    def latest_version(self) -> str | None:
        container = self._container
        status = container.get("update")
        if status == "available":
            return container.get("latest_version")
        if status in ("unknown", "error"):
            return None  # D2HA does not know: HA must not claim "up-to-date"
        return container.get("installed_version")

    @property
    def release_url(self) -> str | None:
        return self._container.get("release_url") or None

    @property
    def in_progress(self) -> bool:
        return self._job is not None

    @property
    def update_percentage(self) -> int | None:
        job = self._job
        if not job:
            return None
        percent = job.get("percent")
        return int(percent) if percent is not None else None

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
            raise d2ha_error("notes_failed", exc.code) from exc
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
            raise d2ha_error("update_failed", exc.code) from exc
        self._active_job = {"id": job_id, "state": "queued"}
        self.async_write_ha_state()
        # The coordinator speeds up while jobs run, so the other entities follow too.
        await self.coordinator.async_request_refresh()
        try:
            await _follow_job(client, job_id, self)
            # Refresh at once (not the debounced request), so the new version
            # shows immediately instead of the old one for about a second.
            await self.coordinator.async_refresh()
        finally:
            self._active_job = None
            self.async_write_ha_state()


async def _follow_job(client, job_id: str, entity: D2HAContainerUpdate) -> None:
    """Poll the job until it ends; the entity shows its progress meanwhile."""
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
        entity._active_job = job
        entity.async_write_ha_state()
        state = job.get("state")
        if state == "done":
            return
        if state == "failed":
            raise d2ha_error("update_failed", job.get("error") or "error.generic")
        await asyncio.sleep(JOB_POLL_INTERVAL)
        elapsed += JOB_POLL_INTERVAL
    raise HomeAssistantError(translation_domain=DOMAIN, translation_key="job_timeout")
