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
