"""The dashboard strategy module, served once per Home Assistant start."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_loaded_integration

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

URL_PATH = f"/{DOMAIN}_frontend"
STRATEGY_FILE = "d2ha-strategy.js"
_FLAG = "frontend_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Serve the strategy and register it with the frontend, once per start."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_FLAG):
        return
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                URL_PATH,
                str(Path(__file__).parent / "frontend"),
                cache_headers=False,
            )
        ]
    )
    if DATA_EXTRA_MODULE_URL in hass.data:
        # The frontend is loaded (any Home Assistant with a UI): the strategy
        # module is added to every page and registers itself in
        # window.customStrategies.
        version = async_get_loaded_integration(hass, DOMAIN).version
        add_extra_js_url(hass, f"{URL_PATH}/{STRATEGY_FILE}?v={version}")
    else:
        _LOGGER.debug("Frontend not loaded: the D2HA dashboard is not offered")
    data[_FLAG] = True
