"""The D2HA integration: container updates and logs in Home Assistant."""

from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import D2HAClient
from .const import CONF_TOKEN, CONF_URL, DOMAIN, REMOVE_AFTER
from .coordinator import D2HACoordinator
from .frontend import async_register_frontend

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["update", "sensor", "button"]

type D2HAConfigEntry = ConfigEntry[D2HACoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: D2HAConfigEntry) -> bool:
    # The strategy module is served before the first refresh: when D2HA is
    # down at start-up the entry goes into setup retry, but a saved D2HA
    # dashboard must still find /d2ha_frontend/d2ha-strategy.js.
    await async_register_frontend(hass)
    client = D2HAClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN]
    )
    coordinator = D2HACoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # The server device exists before the platforms, so container devices can
    # link to it with via_device_id.
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="D2HA",
        manufacturer="Arborae",
        sw_version=coordinator.data.get("info", {}).get("version"),
        configuration_url=client.url,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def update_device_version() -> None:
        """Keep the device version in step with the D2HA it talks to."""
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, entry.entry_id)},
            sw_version=coordinator.data.get("info", {}).get("version"),
        )

    entry.async_on_unload(coordinator.async_add_listener(update_device_version))
    _watch_gone_containers(hass, entry)
    return True


def _container_key(entry: D2HAConfigEntry, device: dr.DeviceEntry) -> str | None:
    """The key of the container behind a device; None for the server device."""
    prefix = f"{entry.entry_id}_"
    for domain, identifier in device.identifiers:
        if domain == DOMAIN and identifier.startswith(prefix):
            return identifier[len(prefix):]
    return None


def _watch_gone_containers(hass: HomeAssistant, entry: D2HAConfigEntry) -> None:
    """Remove the device of a container D2HA has not listed for a day.

    Only the answers of D2HA count: the time it does not answer is not
    absence, and neither is an empty list, more likely a Docker that is
    starting than a server without containers. The count starts again when
    the container is back, and when Home Assistant restarts.
    """
    coordinator = entry.runtime_data
    absent: dict[str, float] = {}  # device id -> seconds of answers without it
    last_answer: float | None = None

    @callback
    def check() -> None:
        nonlocal last_answer
        containers = coordinator.data.get("containers", [])
        if not coordinator.last_update_success or not containers:
            last_answer = None
            return
        # A monotonic clock: a jump of the system time removes nothing.
        now = time.monotonic()
        step = now - last_answer if last_answer is not None else 0.0
        last_answer = now
        keys = {container["key"] for container in containers}
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            key = _container_key(entry, device)
            if key is None or key in keys:
                absent.pop(device.id, None)
                continue
            absent[device.id] = (
                absent[device.id] + step if device.id in absent else 0.0
            )
            if absent[device.id] < REMOVE_AFTER.total_seconds():
                continue
            del absent[device.id]
            _LOGGER.info(
                "Removing the device of %s: D2HA has not listed the container for %s hours",
                device.name_by_user or device.name,
                int(REMOVE_AFTER.total_seconds() // 3600),
            )
            device_registry.async_remove_device(device.id)

    check()
    entry.async_on_unload(coordinator.async_add_listener(check))


async def async_unload_entry(hass: HomeAssistant, entry: D2HAConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: D2HAConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """A container device can be deleted once D2HA no longer lists the container."""
    if entry.state is not ConfigEntryState.LOADED:
        # Without an answer from D2HA there is no telling a removed container.
        return False
    key = _container_key(entry, device_entry)
    return key is not None and entry.runtime_data.container(key) is None
