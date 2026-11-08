"""The dashboard strategy module is served and registered once."""

from __future__ import annotations

import pytest

from conftest import CONTAINERS, INFO, URL, setup_integration

pytestmark = pytest.mark.asyncio


def _fake_frontend_urls(hass):
    """Stand in for the frontend integration (not installable in tests)."""
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL, UrlManager

    manager = UrlManager(lambda *_: None, [])
    hass.data[DATA_EXTRA_MODULE_URL] = manager
    return manager


async def test_strategy_module_is_served(hass, d2ha_server, hass_client):
    """GET on the static path returns the strategy, with the registration."""
    await setup_integration(hass)
    client = await hass_client()
    response = await client.get("/d2ha_frontend/d2ha-strategy.js")
    assert response.status == 200
    text = await response.text()
    assert "ll-strategy-dashboard-d2ha" in text
    assert "customStrategies" in text


async def test_extra_js_url_is_registered(hass, d2ha_server):
    """With a loaded frontend, every page loads the strategy module."""
    manager = _fake_frontend_urls(hass)
    await setup_integration(hass)
    assert any(
        url.startswith("/d2ha_frontend/d2ha-strategy.js?v=")
        for url in manager.urls
    )


async def test_no_extra_js_url_without_a_frontend(hass, d2ha_server):
    """A Home Assistant without the frontend still sets up cleanly."""
    from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL

    await setup_integration(hass)
    assert DATA_EXTRA_MODULE_URL not in hass.data


async def test_registration_happens_once_with_two_servers(hass, d2ha_server):
    """Two config entries share one static path and one extra JS URL."""
    manager = _fake_frontend_urls(hass)
    url_b = "http://d2ha-b.example:12021"
    d2ha_server.get(f"{url_b}/api/v1/info", json=INFO)
    d2ha_server.get(f"{url_b}/api/v1/containers?ha=1", json=CONTAINERS)
    d2ha_server.get(f"{url_b}/api/v1/jobs", json={"jobs": []})
    await setup_integration(hass)
    await setup_integration(hass, url=url_b)
    assert len([url for url in manager.urls if "d2ha_frontend" in url]) == 1


async def test_module_is_served_while_d2ha_is_unreachable(
    hass, d2ha_server, hass_client
):
    """D2HA down at start-up: the entry retries, but the module stays served."""
    import aiohttp

    from homeassistant.config_entries import ConfigEntryState

    manager = _fake_frontend_urls(hass)
    d2ha_server.clear_requests()
    d2ha_server.get(
        f"{URL}/api/v1/info", exc=aiohttp.ClientConnectionError("refused")
    )
    entry = await setup_integration(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    client = await hass_client()
    response = await client.get("/d2ha_frontend/d2ha-strategy.js")
    assert response.status == 200
    assert any(
        url.startswith("/d2ha_frontend/d2ha-strategy.js?v=")
        for url in manager.urls
    )
