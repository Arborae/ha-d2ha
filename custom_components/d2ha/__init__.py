"""The D2HA integration: container updates and logs in Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import D2HAClient
from .const import CONF_TOKEN, CONF_URL, DOMAIN
from .coordinator import D2HACoordinator
from .frontend import async_register_frontend

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["update", "sensor", "button"]

type D2HAConfigEntry = ConfigEntry[D2HACoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: D2HAConfigEntry) -> bool:
    client = D2HAClient(
        async_get_clientsession(hass), entry.data[CONF_URL], entry.data[CONF_TOKEN]
    )
    coordinator = D2HACoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await async_register_frontend(hass)
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: D2HAConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: D2HAConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """A container device can be deleted once D2HA no longer lists the container."""
    if entry.state is not ConfigEntryState.LOADED:
        # Without an answer from D2HA there is no telling a removed container.
        return False
    coordinator = entry.runtime_data
    prefix = f"{entry.entry_id}_"
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN or not identifier.startswith(prefix):
            continue
        return coordinator.container(identifier[len(prefix):]) is None
    return False
