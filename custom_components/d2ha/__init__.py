"""The D2HA integration: container updates and logs in Home Assistant."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import D2HAClient
from .const import CONF_TOKEN, CONF_URL, DOMAIN
from .coordinator import D2HACoordinator

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
