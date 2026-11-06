"""Data update coordinator for the D2HA integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import D2HAAuthError, D2HAClient, D2HAConnectionError, D2HAError
from .const import DOMAIN, SCAN_INTERVAL, SCAN_INTERVAL_ACTIVE

_LOGGER = logging.getLogger(__name__)


class D2HACoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll /info, /containers?ha=1 and /jobs; poll faster while jobs run."""

    def __init__(self, hass: HomeAssistant, client: D2HAClient) -> None:
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL
        )
        self.client = client
        self.data: dict[str, Any] = {"info": {}, "containers": [], "jobs": []}

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            info = await self.client.info()
            containers = await self.client.containers()
            jobs = await self.client.jobs()
        except D2HAAuthError as exc:
            raise ConfigEntryAuthFailed("error.unauthorized") from exc
        except D2HAConnectionError as exc:
            raise UpdateFailed("error.cannot_connect") from exc
        except D2HAError as exc:
            raise UpdateFailed(exc.code) from exc
        active = any(j.get("state") in ("queued", "running") for j in jobs)
        wanted = SCAN_INTERVAL_ACTIVE if active else SCAN_INTERVAL
        if self.update_interval != wanted:
            self.update_interval = wanted
        return {
            "info": info,
            "containers": containers.get("containers", []),
            "jobs": jobs,
        }

    def container(self, key: str) -> dict[str, Any] | None:
        """One container view by its stable key."""
        for container in self.data.get("containers", []):
            if container.get("key") == key:
                return container
        return None

    def job_for(self, key: str, name: str) -> dict[str, Any] | None:
        """The running job updating this container, dedicated or update-all.

        An update-all job updates one container at a time: per API.md its
        ``label`` is the name of the container it is on right now.
        """
        fallback = None
        for job in self.data.get("jobs", []):
            if job.get("state") not in ("queued", "running"):
                continue
            if job.get("kind") == "update" and job.get("target") == key:
                return job
            if job.get("kind") == "update_all" and job.get("label") == name:
                fallback = job
        return fallback
