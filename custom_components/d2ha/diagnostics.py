"""Diagnostics for a D2HA config entry: useful, never private."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN, CONF_URL
from .coordinator import D2HACoordinator

if TYPE_CHECKING:
    from . import D2HAConfigEntry

TO_REDACT = {CONF_URL, CONF_TOKEN}

# Per container only what helps a bug report: no status text or Docker id;
# the key carries stack and container names.
CONTAINER_FIELDS = (
    "key",
    "state",
    "health",
    "update",
    "can_update",
    "has_notes",
    "breaking",
    "is_self",
    "is_proxy",
    "ha",
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: D2HAConfigEntry
) -> dict[str, Any]:
    coordinator: D2HACoordinator = entry.runtime_data
    containers = []
    for container in coordinator.data.get("containers", []):
        item = {field: container.get(field) for field in CONTAINER_FIELDS}
        job = coordinator.job_for(container.get("key"), container.get("name") or "")
        if job:
            # The job label (a container name) stays out on purpose.
            item["active_job"] = {
                "id": job.get("id"),
                "kind": job.get("kind"),
                "state": job.get("state"),
                "percent": job.get("percent"),
            }
        containers.append(item)
    return {
        "entry": async_redact_data(entry.data, TO_REDACT),
        "info": coordinator.data.get("info", {}),
        "containers": containers,
    }
