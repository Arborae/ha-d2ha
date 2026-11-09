"""The config flow: URL + token, clear errors, re-authentication."""

from __future__ import annotations

import aiohttp
import pytest

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType

from custom_components.d2ha.const import DOMAIN

from conftest import URL, setup_integration

pytestmark = pytest.mark.asyncio


async def test_full_flow(hass, d2ha_server):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "d2ha.example:12021/", "token": "test-token"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "D2HA"
    # The address is normalized: scheme added, trailing slash removed.
    assert result["data"]["url"] == URL


async def test_wrong_token(hass, d2ha_server):
    d2ha_server.clear_requests()
    d2ha_server.get(f"{URL}/api/v1/info", status=401, json={"error": "unauthorized"})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": URL, "token": "wrong"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_unreachable(hass, d2ha_server):
    d2ha_server.get(
        "http://127.0.0.1:9/api/v1/info",
        exc=aiohttp.ClientConnectionError("refused"),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "http://127.0.0.1:9", "token": "x"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_with_a_new_token(hass, d2ha_server):
    entry = await setup_integration(hass)
    entry.async_start_reauth(hass)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"token": "new-token"}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["token"] == "new-token"


async def test_reconfigure_with_a_new_address(hass, d2ha_server):
    """The address changes with the unique id; entities and token stay."""
    from homeassistant.helpers import entity_registry as er

    from conftest import CONTAINERS, INFO, TOKEN

    new_url = "http://d2ha-new.example:12021"
    d2ha_server.get(f"{new_url}/api/v1/info", json=INFO)
    d2ha_server.get(f"{new_url}/api/v1/containers?ha=1", json=CONTAINERS)
    d2ha_server.get(f"{new_url}/api/v1/jobs", json={"jobs": []})
    entry = await setup_integration(hass)
    registry = er.async_get(hass)
    before = {
        entity_id: registry.async_get(entity_id).unique_id
        for entity_id in (
            "sensor.d2ha_updates_available",
            "update.jellyfin_update",
            "button.d2ha_update_all",
        )
    }
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "d2ha-new.example:12021/", "token": ""}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["url"] == new_url  # normalized, like in the user step
    assert entry.unique_id == new_url
    assert entry.data["token"] == TOKEN  # empty kept the current one
    await hass.async_block_till_done()
    for entity_id, unique_id in before.items():
        assert registry.async_get(entity_id).unique_id == unique_id
    assert hass.states.get("sensor.d2ha_updates_available").state == "1"


async def test_reconfigure_with_a_wrong_token(hass, d2ha_server):
    entry = await setup_integration(hass)
    d2ha_server.clear_requests()
    d2ha_server.get(f"{URL}/api/v1/info", status=401, json={"error": "unauthorized"})
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": URL, "token": "wrong"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["url"] == URL


async def test_reconfigure_unreachable(hass, d2ha_server):
    d2ha_server.get(
        "http://127.0.0.1:9/api/v1/info",
        exc=aiohttp.ClientConnectionError("refused"),
    )
    entry = await setup_integration(hass)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": "http://127.0.0.1:9", "token": ""}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_to_an_address_already_used(hass, d2ha_server):
    """Two entries must not point at the same D2HA."""
    from conftest import CONTAINERS, INFO

    url_b = "http://d2ha-b.example:12021"
    d2ha_server.get(f"{url_b}/api/v1/info", json=INFO)
    d2ha_server.get(f"{url_b}/api/v1/containers?ha=1", json=CONTAINERS)
    d2ha_server.get(f"{url_b}/api/v1/jobs", json={"jobs": []})
    entry = await setup_integration(hass)
    await setup_integration(hass, url=url_b)
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"url": url_b, "token": ""}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
